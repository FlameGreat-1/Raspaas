const plugin = require('tailwindcss/plugin')

module.exports = plugin(function ({ addComponents }) {
  addComponents({
    '.f-nav-item li a': {
      '@apply text-base hover:ml-1 hover:text-white/70  transition-all ease-in-out duration-300 inline-block py-1.5 dark:text-gray-20 dark:hover:text-white': {},
    },
  })
})
