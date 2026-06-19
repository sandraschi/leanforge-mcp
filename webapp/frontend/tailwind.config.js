/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f1117",
        "surface-2": "#1a1d27",
        border: "#2a2d3a",
        accent: "#6366f1",
      },
    },
  },
  plugins: [],
};
