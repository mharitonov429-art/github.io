// Конфиг для сборки CSS (Tailwind standalone CLI v3). Запускается из корня репозитория в GitHub Actions.
module.exports = {
  content: ['./dist/**/*.html'],
  theme: { extend: {} },
  plugins: [require('@tailwindcss/typography')],
};
