/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: { colors: {
    ink: "rgb(var(--ink-rgb) / <alpha-value>)", prussian: "rgb(var(--prussian-rgb) / <alpha-value>)",
    regal: "rgb(var(--regal-rgb) / <alpha-value>)", linen: "rgb(var(--linen-rgb) / <alpha-value>)",
    jungle: "rgb(var(--jungle-rgb) / <alpha-value>)", tomato: "rgb(var(--tomato-rgb) / <alpha-value>)",
    amber: "rgb(var(--amber-rgb) / <alpha-value>)", surface: "#F4F0E8", raised: "#FBF9F4",
  }, fontFamily: { sans: ["DM Sans", "system-ui", "sans-serif"] },
  borderRadius: { card: "20px", control: "12px" },
  boxShadow: { soft: "0 1px 2px rgba(8,22,39,.05), 0 8px 24px rgba(8,22,39,.06)" },
  } },
  plugins: [],
};
