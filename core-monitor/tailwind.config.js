/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'status-healthy': '#10b981',
        'status-unhealthy': '#ef4444',
        'status-starting': '#f59e0b',
      },
    },
  },
  plugins: [],
}

