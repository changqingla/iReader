/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./web/pages/**/*.{js,ts,jsx,tsx}",
    "./web/components/**/*.{js,ts,jsx,tsx}",
    "./web/hooks/**/*.{js,ts,jsx,tsx}",
    "./web/lib/**/*.{js,ts,jsx,tsx}",
    "./web/utils/**/*.{js,ts,jsx,tsx}",
    "./web/App.tsx",
    "./web/main.tsx"
  ],
  theme: {
    container: {
      center: true,
    },
    extend: {},
  },
  plugins: [],
};
