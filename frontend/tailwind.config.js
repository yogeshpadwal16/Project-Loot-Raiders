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
        canvas: '#070a12',
        surface: {
          DEFAULT: '#0f1623',
          hover: '#172033',
          elevated: '#1e293b',
          overlay: '#0f172a',
        },
        border: {
          subtle: 'rgba(255, 255, 255, 0.07)',
          DEFAULT: 'rgba(255, 255, 255, 0.12)',
          focus: '#f59e0b',
        },
        brand: {
          DEFAULT: '#f59e0b',
          hover: '#d97706',
          glow: 'rgba(245, 158, 11, 0.15)',
          teal: '#10b981',
        },
        merchant: {
          amazon: '#ff9900',
          flipkart: '#2874f0',
          myntra: '#ff3f6c',
          ajio: '#2c4152',
          telegram: '#0088cc'
        },
        status: {
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          info: '#3b82f6',
          verified: '#10b981',
          glitch: '#ef4444',
          discount: '#f59e0b'
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'glow-amber': '0 0 20px -5px rgba(245, 158, 11, 0.3)',
        'glow-teal': '0 0 20px -5px rgba(16, 185, 129, 0.3)',
        'glow-subtle': '0 4px 20px -2px rgba(0, 0, 0, 0.6)',
      }
    },
  },
  plugins: [],
}
