const plugin = require('tailwindcss/plugin');

module.exports = plugin(function ({ addComponents }) {
  addComponents({
    '.text-contain': {
      '@apply text-gray-100 dark:text-mute-500': {},
    },
    // direction
    '.dir-left': {
      '@apply w-16 h-11 text-sm text-white fixed right-0 top-1/2 -translate-y-1/2 z-30': {},
    },
    //corporate
    '.corporate-title': {
      '@apply text-2xl md:text-3xl xl:text-4xl  xl:leading-[50px] dark:text-white dark:opacity-90 capitalize': {},
    },
    //beauty
    '.beauty-title': {
      '@apply text-4xl lg:text-5xl font-marcellus leading-[50px] lg:leading-[70px] dark:text-white dark:opacity-90 capitalize': {},
    },
    //architecture
    '.architecture-title': {
      '@apply text-4xl lg:text-5xl lg:leading-[60px] font-extrabold dark:text-white dark:opacity-90 capitalize': {},
    },
  });
});
