import pandas as pd
from google.cloud import documentai_v1 as documentai
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")
genai.configure(api_key=api_key)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'gcp_creds.json'

main_df_columns = ["CLIENT", "COMPANY", "DESCRIPTION", "INVOICE_ID", "NET_AMOUNT", "VAT_AMOUNT", "TOTAL_AMOUNT"]
main_df = pd.DataFrame(columns=main_df_columns)

def refine_description(description):
  model = genai.GenerativeModel(model_name='gemini-1.5-flash')
  safe = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
  ]


  response = model.generate_content(
      f"""This text contains descriptions of items extracted from an invoice. Each new item description is comma separated. Although this is not necessary that after comma there must be information for new item, it can be contain extra info comma seprated so you have to double check if its item or some other stuff. A description can contain single item name or multiple item name. Each description have noises like \n or irrelevant text etc. In most cases text coming after \n is not about item name but its about item information and other stuff which is irrelevant for us. So check if you find potential item name after \n take it otherwise ignore it.
  For each item description, identify the most likely name of the item. The item name can be a single word or a phrase. Give me only the name form it, I dont want any explanation. and if there are multiple name give me in single line comma separated.
  NOTE: DOUBLE CHECK IF YOU ARE MISSING ANY ITEM NAME OR NOT. IF YES THEN MUST ADD IT.

  {description}
  """, safety_settings= safe)

  cleaned_response = " ".join(response.text.split())

  return cleaned_response

def convert_amount(raw_value):
    if ('.' not in raw_value and ',' in raw_value ) and (raw_value.count(',') == 1):
        if len(raw_value.split(',')[1]) == 3:
            raw_value = raw_value.replace(',', '')
        else:
            raw_value = raw_value.replace(',', '.')
    elif ('.' in raw_value and ',' in raw_value ) and (raw_value.find(',') > raw_value.find('.')):
        raw_value = raw_value.replace('.', '').replace(',', '.')
    else:
        raw_value = raw_value.replace(',', '')

    try:
        return float(raw_value)
    except ValueError:
        return None

def extract_and_insert(api_df):
    type_to_columns = {
        "CLIENT": ["receiver_name", "ship_to_name","ship_to_address","remit_to_name"],
        "COMPANY": ["supplier_name","company"],
        "DESCRIPTION": ["line_item/description"],
        "INVOICE_ID": ["invoice_id"],
        "NET_AMOUNT": ["net_amount"],
        "VAT_AMOUNT": ["vat/tax_amount","total_tax_amount"],
        "TOTAL_AMOUNT": ["total_amount"]
    }

    new_data = {col: None for col in main_df_columns}

    for _, row in api_df.iterrows():
        type_ = row["Type"]
        raw_value = row["Raw Value"]

        for column_name, types in type_to_columns.items():
            if type_ in types:
                if column_name == "DESCRIPTION":
                    if new_data[column_name]:
                        new_data[column_name] += ", " + refine_description(raw_value)
                    else:
                        new_data[column_name] = refine_description(raw_value)
                elif new_data[column_name] is None:
                    if column_name in ["NET_AMOUNT", "VAT_AMOUNT", "TOTAL_AMOUNT"]:
                        new_data[column_name] = convert_amount(raw_value)
                    else:
                        new_data[column_name] = raw_value
        
    for col_name in ["CLIENT", "COMPANY", "VAT_AMOUNT"]:
        if new_data[col_name] is None:
            for type_ in type_to_columns[col_name]:
                match = api_df[api_df["Type"] == type_]
                if not match.empty:
                    new_data[col_name] = match.iloc[0]["Raw Value"]
                    break

    if new_data["VAT_AMOUNT"] is None:
        net_amount = new_data["NET_AMOUNT"]
        total_amount = new_data["TOTAL_AMOUNT"]
        if net_amount is not None and total_amount is not None:
            new_data["VAT_AMOUNT"] = total_amount - net_amount

    if new_data["TOTAL_AMOUNT"] is None:
        net_amount = new_data["NET_AMOUNT"]
        vat_amount = new_data["VAT_AMOUNT"]
        if net_amount is not None and vat_amount is not None:
            new_data["TOTAL_AMOUNT"] = net_amount + vat_amount

    return new_data

def online_process(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str,
) -> documentai.Document:
    """
    Processes a document using the Document AI Online Processing API.
    """

    opts = {"api_endpoint": f"{location}-documentai.googleapis.com"}

    documentai_client = documentai.DocumentProcessorServiceClient(client_options=opts)

    resource_name = documentai_client.processor_path(project_id, location, processor_id)

    with open(file_path, "rb") as file:
        file_content = file.read()

    raw_document = documentai.RawDocument(content=file_content, mime_type=mime_type)

    request = documentai.ProcessRequest(name=resource_name, raw_document=raw_document)

    result = documentai_client.process_document(request=request)

    return result.document

def main_process(temp_file_path):
  PROJECT_ID = os.getenv("GCP_PROJECT_ID")
  LOCATION = "us"  # Format is 'us' or 'eu'
  PROCESSOR_ID = os.getenv("PROCESSOR_ID")  

  FILE_PATH = temp_file_path
  MIME_TYPE = "image/jpeg"

  document = online_process(
      project_id=PROJECT_ID,
      location=LOCATION,
      processor_id=PROCESSOR_ID,
      file_path=FILE_PATH,
      mime_type=MIME_TYPE,
  )

  types = []
  raw_values = []
  normalized_values = []
  confidence = []

  for entity in document.entities:
      types.append(entity.type_)
      raw_values.append(entity.mention_text)
      normalized_values.append(entity.normalized_value.text)
      confidence.append(f"{entity.confidence:.0%}")

      for prop in entity.properties:
          types.append(prop.type_)
          raw_values.append(prop.mention_text)
          normalized_values.append(prop.normalized_value.text)
          confidence.append(f"{prop.confidence:.0%}")

  df = pd.DataFrame(
      {
          "Type": types,
          "Raw Value": raw_values,
          "Normalized Value": normalized_values,
          "Confidence": confidence,
      }
  )

  main_df = extract_and_insert(df)
  main_df = pd.DataFrame([main_df])
  main_df.to_csv("output.csv", index=False)
  return "output.csv"