const plugin = require('tailwindcss/plugin')

module.exports = plugin(function ({ addComponents }) {
  addComponents({
    // responaive 
    '.responsive-nav-item ul li a': {
      '@apply text-base inline-block px-3 py-2 capitalize dark:text-gray-20 hover:text-black/50': {},
    },
    '.header-nav li a': {
      '@apply text-base inline-block px-5 py-2.5 capitalize': {},
    },
    '.nav-item ul li a': {
      '@apply text-base inline-block px-5 py-2 capitalize dark:text-gray-20 dark:hover:text-white  hover:-translate-x-1 transition-all ease-in-out duration-300 hover:text-black/50 relative after:absolute after:bg-black/30 dark:after:bg-white/50 after:bottom-0 after:left-0 after:w-0  after:h-[1px] hover:after:w-full after:transition-all after:duration-300 after:ease-in-out': {},
    },
    // restorunt 
    '.res-nav-item ul li a': {
      '@apply text-base inline-block px-3 py-2 capitalize dark:text-gray-20 hover:text-white': {},
    },
    //nav list animation
    '.nav-hover': {
      '@apply  transition-all ease-in-out duration-300 relative after:absolute after:bottom-0 after:right-0 after:w-0 after:left-[initial]  hover:after:left-0 hover:after:w-full hover:after:right-[initial] after:h-[1px] after:transition-all after:duration-300 after:ease-in-out': {},
    },
    //music
    '.music-nav-item li a': {
      '@apply px-0 py-2 capitalize hover:text-blue-500 dark:text-white': {},
    },
    //marketing
    '.marketing-nav li a': {
      '@apply px-0 py-2 capitalize dark:text-white': {},
    },
    '.marketing-nav-item ul li a': {
      '@apply text-base text-black/70 hover:text-[#a3c3c7] dark:text-gray-20 dark:hover:text-[#a3c3c7] transition-all ease-in-out duration-300 inline-block px-5 py-2 block': {},
    },
    //beauty
    '.beauty-nav-item ul li a': {
      '@apply text-base hover:text-orange-50 dark:text-gray-20 dark:hover:text-white transition-all ease-in-out duration-300 inline-block px-5 py-2': {},
    },
    // architecture 
    '.architecture-nav-item ul li a': {
      '@apply text-base hover:text-lime-500  hover:pl-1 transition-all ease-in-out duration-300 inline-block px-5 py-2': {},
    },
    //hosting
    '.hosting-nav li a': {
      '@apply px-0 py-2 capitalize dark:text-blue-400': {},
    },
    '.hosting-nav-item ul li a': {
      '@apply text-base text-black/70 hover:text-blue-500 dark:text-gray-20 dark:hover:text-blue-500 transition-all ease-in-out duration-300 inline-block px-5 py-2 block': {},
    },
    //charity
    '.charity-nav li a': {
      '@apply px-0 py-1 capitalize dark:text-white': {},
    },
    '.charity-nav-item ul li a': {
      '@apply text-base text-black/70 hover:text-green-600 dark:text-gray-20 dark:hover:text-green-600 transition-all ease-in-out duration-300 inline-block px-5 py-2 block': {},
    },
    //yoga nav list animation
    '.yoga-nav-hover': {
      '@apply  transition-all ease-in-out duration-300 relative after:absolute after:bottom-0 after:right-0 after:w-full  after:h-[1px] after:scale-x-0 hover:after:scale-x-100 after:transition-all after:duration-300 after:ease-in-out': {},
    },
    // yoga 
    '.yoga-nav li a': {
      '@apply px-0 py-1 capitalize dark:text-white': {},
    },
    '.yoga-nav-item ul li a': {
      '@apply text-base text-black/70 hover:text-purple-600 dark:text-gray-20 dark:hover:text-purple-600 transition-all ease-in-out duration-300 inline-block px-5 py-2 block': {},
    },
    // cyptocurrency 
    //yoga nav list animation
    '.crypto-nav-hover': {
      '@apply  transition-all ease-in-out duration-300 relative after:absolute after:top-0 after:right-0 after:w-full  after:h-[1px] after:scale-x-0 hover:after:scale-x-100 after:transition-all after:duration-300 after:ease-in-out': {},
    },
    '.crypto-nav li a': {
      '@apply px-0 py-1 uppercase dark:text-white': {},
    },
    '.crypto-nav-item ul li a': {
      '@apply text-base text-black hover:text-lime-400 dark:text-white dark:hover:text-lime-400 transition-all ease-in-out duration-300 inline-block px-5 py-2 block': {},
    },
    '.crypto-nav-hover': {
      '@apply  transition-all ease-in-out duration-300 relative after:absolute after:bottom-0 after:right-0 after:w-0  after:h-[1px] hover:after:w-full after:transition-all after:duration-300 after:ease-in-out': {},
    },
    // fashion 
    '.fashion-nav-item ul li a': {
      '@apply text-base text-black hover:text-cyan-700 dark:text-white dark:hover:text-cyan-700 transition-all ease-in-out duration-300 inline-block px-5 py-2 block': {},
    },
    // decor 
    '.decor-nav-hover': {
      '@apply  transition-all ease-in-out duration-300 relative after:absolute after:bottom-0 after:right-0 after:w-full  after:h-[1px] after:scale-x-0 hover:after:scale-x-100 after:transition-all after:duration-300 after:ease-in-out': {},
    },
  })
})
