/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0a0f',
          secondary: '#12121a',
          card: '#16161f',
          hover: '#1e1e2a',
        },
        accent: {
          cyan: '#00d4ff',
          violet: '#7c3aed',
          pink: '#e879f9',
          green: '#10b981',
          amber: '#f59e0b',
        },
        text: {
          primary: '#f0f0ff',
          secondary: '#8888aa',
          muted: '#55556a',
        },
        border: {
          DEFAULT: '#1e1e2a',
          bright: '#2a2a3a',
        },
      },
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        body: ['DM Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-up': 'fadeUp 0.5s ease forwards',
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
    },
  },
  plugins: [],
}
