import axios from "axios";
import { useState } from "react";

function App() {
  const [invoiceImage, setInvoiceImage] = useState(null);
  const [isFormSubmitting, setIsFormSubmitting] = useState(false);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setInvoiceImage(file);
    }
  };

  const onSubmit = async () => {
    setIsFormSubmitting(true);
    try {
      setIsFormSubmitting(true);
      const formData = new FormData();
      formData.append("file", invoiceImage);

      const response = await axios.post(
        "http://localhost:8000/process_image",
        formData,
        {
          responseType: "blob",
        }
      );

      const blob = new Blob([response.data], { type: "text/csv" });

      const link = document.createElement("a");
      const url = window.URL.createObjectURL(blob);
      link.href = url;
      link.setAttribute("download", "output.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setIsFormSubmitting(false);
    } catch (error) {
      console.error("Error downloading CSV:", error);
      setIsFormSubmitting(false);
    }
  };

  return (
    <div className="p-2">
      <div>
        <h1 className="font-bold text-3xl">Extractify</h1>
        <p className="italic">Invoice data extractor</p>
      </div>
      <div className="bg-brand-primary py-2 px-1">
        <p className="font-bold text-lg">Upload your invoice picture here!</p>
        <form className="flex justify-center items-center gap-4">
          <input
            type="file"
            name="invoice"
            id="invoice"
            accept="image/jpg, image/jpeg"
            className="border-2 border-black rounded"
            onChange={handleFileChange}
          />
          <input
            type="button"
            value={isFormSubmitting ? "Processing" : "Submit"}
            onClick={onSubmit}
            disabled={isFormSubmitting}
            className="bg-slate-950 text-white rounded-md w-fit px-4 py-2"
          />
        </form>
        {isFormSubmitting && (
          <p>
            Your invoice is being processed by our AI, your download will start
            soon
          </p>
        )}
      </div>

      <div className="bg-blue-300 flex items-center justify-center">
        {invoiceImage && (
          <div className="flex flex-col py-4">
            <p className="text-lg mb-1">Your uploaded image:</p>
            <img
              className="w-96"
              src={URL.createObjectURL(invoiceImage)}
              alt="Preview"
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
