/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        notion: {
          bg: "#f7f6f3",
          card: "#ffffff",
          text: "#37352f",
          muted: "#6b6b6b",
          light: "#9ca3af",
          border: "#e9e9e7",
        },
      },
    },
  },
  plugins: [],
};
