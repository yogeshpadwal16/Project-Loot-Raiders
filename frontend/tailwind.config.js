/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'var(--color-bg)',
        surface: 'var(--color-surface)',
        'surface-border': 'var(--color-border)',
        primary: {
          50: '#fff7ed',
          100: '#ffedd5',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c'
        },
        merchant: {
          amazon: '#ff9900',
          flipkart: '#2874f0',
          myntra: '#ff3f6c',
          telegram: '#0088cc'
        },
        status: {
          verified: '#22c55e',
          glitch: '#ef4444',
          discount: '#ea580c'
        }
      }
    },
  },
  plugins: [],
}
