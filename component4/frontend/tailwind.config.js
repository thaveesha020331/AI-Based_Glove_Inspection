/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#132238",
        muted: "#627089",
        line: "#e4eaf1",
        canvas: "#f6f8fb",
        brand: "#1d6b8f",
        teal: "#168b87",
      },
      boxShadow: {
        soft: "0 8px 24px rgba(19, 34, 56, 0.06)",
      },
    },
  },
  plugins: [],
};
