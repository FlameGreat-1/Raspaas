const plugin = require('tailwindcss/plugin')

module.exports = plugin(function ({ addComponents, theme }) {
  addComponents({
    '.swiper-pagination ': {
      '@apply w-3 h-3 mx-2': {},
    },
    '.swiper-arrows .swiper-button-disabled': {
      '@apply  opacity-30 cursor-not-allowed': {},

    },
    // corporate
    '.corporate-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 rounded-none transform rotate-45 border-sky-500 dark:border-sky-300 border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-sky-500 dark:bg-sky-300 border-sky-500 dark:border-sky-300 transform': {},
        }
      },
    },
    // consulting
    '.consulting-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply  w-2 h-2 mx-1 border-[#a78f6b] rounded-none border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-[#a78f6b] border-[#a78f6b] w-10 rounded-l-full': {},
        }
      },
    },
    // wedding
    '.wedding-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 border-[#a78f6b] border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-[#a78f6b] border-[#a78f6b]': {},
        }
      },
    },
    // agency
    '.banner-agency-pagination': {
      '.swiper-pagination': {
        '@apply gap-10': {},
      },
      '.swiper-pagination-bullet': {
        '@apply  flex-shrink-0  w-2 h-2 mx-1 border-white rounded-full border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-white bg-white w-10 rounded-full rounded-l-full': {},
        }
      },
    },
    '.business-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply   w-2 h-2 mx-1 border-blue-500 rounded-full border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-gradient-to-r from-cyan-500 to-blue-500 w-10 rounded-full rounded-l-full': {},
        }
      },
    },
    '.agency-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply   w-2 h-2 mx-1 border-violet-200 rounded-full border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-gradient-to-r from-violet-200/50 to-pink-200/20 w-10 rounded-full rounded-l-full': {},
        }
      },
    },
    //book
    '.bookReview': {
      '.swiper-slide': {
        '@apply transform scale-90 rounded-xl': {},
        '&.swiper-slide-active': {
          '@apply transform scale-100 bg-purple-500 text-white transition-all duration-300 ease-in-out': {},
        },
      },
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 border-purple-500 border-2 opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-purple-500 border-purple-500': {},
        }
      },
    },
    // restaurant
    '.restaurant-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 border-white border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-red-500 border-white': {},
        }
      },
    },
    //medical
    '.medical-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-blue-900 dark:border-white border opacity-100 bg-transparent w-3 h-3': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-white border-blue-900 dark:border-white before:block before:absolute before:w-1.5 before:h-1.5 before:rounded-full before:bg-black relative inline-block before:top-1/2 before:left-1/2 before:-translate-x-1/2 before:-translate-y-1/2 before:transform': {},
        }
      },
    },
    '.medical-pagination-light.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-white border opacity-100 bg-transparent w-3 h-3': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-transparent border-white before:block before:absolute before:w-1.5 before:h-1.5 before:rounded-full before:bg-white relative inline-block before:top-1/2 before:left-1/2 before:-translate-x-1/2 before:-translate-y-1/2 before:transform': {},
        }
      },
    },
    // photography
    '.photography-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-yellow-800 dark:border-white mx-3 border opacity-100 bg-transparent w-3 h-3': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-white dark:bg-transparent border-yellow-800 dark:border-white before:block before:absolute before:w-10 before:h-px before:rounded-full before:bg-yellow-800 dark:before:bg-white relative inline-block before:top-1/2 before:left-1/2 before:-translate-x-1/2 before:-translate-y-1/2 before:transform': {},
        }
      },
    },
    //pizza-pagination
    '.pizza-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 border-black dark:border-white border opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-black/50 dark:border-white dark:bg-white w-8 rounded-md border-black/50': {},
        }
      },
    },
    // hotel
    '.hService': {
      '.swiper-slide': {
        '@apply transform scale-90 rounded-xl transition-all duration-500 ease-in-out': {},
        '.serviceText': {
          '@apply opacity-0 transition-all duration-500 ease-in-out': {},
        },
        '&.swiper-slide-active': {
          '@apply transform scale-100 transition-all duration-500 ease-in-out': {},
          '.serviceText': {
            '@apply opacity-100 transition-all duration-500 ease-in-out': {},
          },
        },
      },
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 border-purple-500 border-2 opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-purple-500 border-purple-500': {},
        }
      },
    },
    '.hotel-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-white dark:border-white transition-all duration-300 ease-in-out border-[2px] opacity-100 bg-transparent w-4 h-4 transform scale-50 flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100': {},
        }
      },
    },
    '.hotel-paginations.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-blue-850 dark:border-white border-[1px] opacity-100 bg-transparent w-4 h-4 transform scale-50 flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100': {},
        }
      },
    },
    // gym 
    '.gym-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-red-600 skew-x-12 dark:border-red-700 rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-2 transform scale-50 flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100 w-12 h-2': {},
        }
      },
    },
    '.gym-r-pegination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-red-600 skew-x-12 dark:border-red-700 rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-2 transform scale-50 flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100 w-12 h-2': {},
        }
      },
    },
    // charity 
    '.charity-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-green-600 dark:border-green-700 rounded-full transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-4 transform scale-50 flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100 w-10 h-10 translate-y-2': {},
        }
      },
    },
    '.c-blog-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-green-600 dark:border-green-700 rotate-45 rounded-none transition-all duration-300 ease-in-out border-[2px] opacity-100 bg-transparent w-2 h-2 transform flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-4 h-4 -translate-y-2': {},
        }
      },
    },

    // yoga 
    '.yoga-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-pink-800 dark:border-pink-600 rounded-full transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-2 transform  flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-2 h-2 bg-pink-800': {},
        }
      },
    },
    //book
    '.appslider': {
      '.swiper-slide': {
        '@apply transform scale-90 rounded-xl': {},
        '&.swiper-slide-active': {
          '@apply transform scale-110 border border-lime-400 rounded-lg p-2 text-white transition-all duration-300 ease-in-out': {},
        },
      },
      '.swiper-pagination-bullet': {
        '@apply  w-2.5 h-2.5 mx-2 border-purple-500 border-2 opacity-100 bg-transparent': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-purple-500 border-purple-500': {},
        }
      },
    },
    // elder 
    '.elder-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-purple-400  rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-4 transform scale-50 rounded-full flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100 w-4 h-4 bg-purple-400': {},
        }
      },
    },
    // barber
    '.barber-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-yellow-600 rounded-none mx-3 border opacity-100 bg-transparent w-2 h-2': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-yellow-600 dark:bg-transparent border-yellow-600 before:block before:absolute before:w-10 before:h-px before:bg-yellow-600 relative inline-block before:top-1/2 before:left-1/2 before:-translate-x-1/2 before:-translate-y-1/2 before:transform': {},
        }
      },
    },
    // lawyer
    '.lawyer-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-yellow-600 rounded-full mx-3 border opacity-100 bg-transparent w-2 h-2': {},

        '&.swiper-pagination-bullet-active': {
          '@apply bg-yellow-600 dark:bg-transparent border-yellow-600 before:block before:absolute before:w-6 before:h-px before:bg-yellow-600 relative inline-block before:top-1/2 before:left-1/2 before:-translate-x-1/2 before:-translate-y-1/2 before:transform rounded-full': {},
        }
      },
    },
    // application 
    '.app-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-teal-600  rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-4 transform scale-50 rounded-full flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100 w-4 h-4 bg-teal-600': {},
        }
      },
    },
    // STARTUP 
    '.startup-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-white rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-2 h-4 transform rounded-full': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-2 h-10 bg-white': {},
        }
      },
    },
    '.start-up-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-blue-300 dark:border-blue-500 rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-4 h-4 transform scale-50 rounded-lg flex-shrink-0': {},

        '&.swiper-pagination-bullet-active': {
          '@apply scale-100 w-4 h-4 bg-blue-300 dark:bg-blue-500': {},
        }
      },
    },
    // green energy 
    '.green-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-white rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-2 h-2 transform rounded-full': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-2 h-2 bg-white': {},
        }
      },
    },
    '.energy-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply border-green-900 dark:border-green-500 rounded-none transition-all duration-500 ease-out border-[2px] opacity-100 bg-transparent w-2 h-2 transform rounded-full': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-2 h-2 bg-green-900 dark:bg-green-500': {},
        }
      },
    },
    '.data-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply bg-purple-500 dark:bg-purple-300 opacity-50 rounded-none transition-all duration-500 ease-out opacity-100 w-2 h-2 transform rounded-full': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-3 h-3 bg-purple-500 dark:bg-purple-300 opacity-100': {},
        }
      },
    },
    '.brand-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply bg-teal-400 opacity-50 rounded-none transition-all duration-500 ease-out opacity-100 w-10 h-2 transform rounded-full': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-4 h-2 bg-teal-600 opacity-100': {},
        }
      },
    },
    '.branding-pagination.swiper-pagination': {
      '.swiper-pagination-bullet': {
        '@apply bg-teal-400 opacity-50 rounded-none transition-all duration-500 ease-out opacity-100 w-2 h-2 transform rounded-full': {},

        '&.swiper-pagination-bullet-active': {
          '@apply w-2 h-2 bg-teal-500 opacity-100': {},
        }
      },
    },
  })
})