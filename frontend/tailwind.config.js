/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'beige': {
          50: '#FDFCFB',
          100: '#F7F5F2',
          200: '#EAE7E3',
          300: '#D9B89B',
          400: '#E6C7A9',
          500: '#C9A88B',
        },
        'charcoal': {
          100: '#6B6B6B',
          200: '#1F1F1F',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
