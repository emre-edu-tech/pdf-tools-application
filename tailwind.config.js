/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/js/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#F4F6FA',
          100: '#E4E9F2',
          200: '#C7D1E3',
          300: '#9DADC9',
          400: '#6D80A8',
          500: '#4D5F8A',
          600: '#3A496D',
          700: '#2E3A57',
          800: '#212A3F',
          900: '#101B33',
          950: '#0A1122',
        },
        accent: {
          50: '#EEFBF9',
          100: '#D3F4EE',
          200: '#A6E8DD',
          300: '#6FD6C6',
          400: '#3DBBA9',
          500: '#0FA294',
          600: '#0D9488',
          700: '#0A6259',
          800: '#0A4E47',
          900: '#08403B',
        },
      },
    },
  },
  plugins: [],
};
