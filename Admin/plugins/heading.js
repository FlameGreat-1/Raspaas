const plugin = require('tailwindcss/plugin')

module.exports = plugin(function({ addBase, theme }) {
    addBase({
       'p': { fontSize: theme('fontSize.base'),},
  })
})

