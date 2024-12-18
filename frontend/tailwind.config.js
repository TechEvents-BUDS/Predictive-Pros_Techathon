/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: "#5ADBFF",
          secondary: "#FFDD4A",
          accent: "#FE9000",
        },
      },
    },
  },
  plugins: [],
};
