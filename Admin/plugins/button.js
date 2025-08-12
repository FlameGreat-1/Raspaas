const plugin = require('tailwindcss/plugin')

module.exports = plugin(function ({ addComponents }) {
    addComponents({
        '.btn': {
            '@apply inline-block py-[0.5625rem] py-3 lg:py-3.5 px-10 lg:px-14 text-center border rounded-md border-transparent bg-transparent text-sm transition-all duration-200 ease-linear': {},
        },
        // corporate-btn
        '.corporate-btn': {
            '@apply border rounded-full border-sky-500 text-white bg-sky-500 hover:bg-white font-semibold hover:text-sky-500 transition-all duration-500 ease-in-out': {},
        },
        //marketing
        '.marketing-outline-btn': {
            '@apply bg-transparent border border-black text-black relative py-3.5 px-10 uppercase tracking-wider font-medium transition-all duration-500 ease-in-out cursor-pointer after:absolute after:bottom-0 after:right-0 after:w-2.5 after:h-2.5 after:bg-mute-200 group-hover:after:w-full group-hover:after:h-full after:transition-all after:duration-500 after:ease-in-out after:-z-10 inline-block z-0 group-hover:bg-lime-50 overflow-hidden group-hover:text-white dark:border-white dark:text-white dark:hover:text-black  dark:after:bg-white': {},
        },
        // architecture
        '.architecture-btn': {
            '@apply bg-lime-500 relative py-3.5 px-14 uppercase tracking-wider font-medium transition-all duration-500 ease-in-out cursor-pointer before:absolute before:top-0 before:left-0 before:w-0 before:h-1/2 before:bg-mute-200 group-hover:before:w-full before:transition-all before:duration-500 before:ease-in-out before:-z-10 after:absolute after:bottom-0 after:right-0 after:w-0 after:h-1/2 after:bg-mute-200 group-hover:after:w-full after:transition-all after:duration-500 after:ease-in-out after:-z-10 inline-block z-0 group-hover:bg-lime-50 overflow-hidden text-white': {},
        },
        //accounting
        '.accounting-btn': {
            '@apply bg-transparent border-0 bg-gray-200 rounded-none border-black text-black relative py-3.5 px-10 uppercase tracking-wider font-medium transition-all duration-500 ease-in-out cursor-pointer after:absolute after:left-0 after:top-0 after:w-[2px] after:h-full after:bg-mute-200 group-hover:after:w-full group-hover:after:h-full after:transition-all after:duration-500 after:ease-in-out after:-z-10 inline-block z-0 group-hover:text-white overflow-hidden': {},
        },
        // ebook
        '.ebook-btn': {
            '@apply bg-purple-500 relative py-3.5 px-14 uppercase tracking-wider font-medium transition-all duration-500 ease-in-out cursor-pointer before:absolute before:top-0 before:left-0 before:w-6 before:h-1/2 before:bg-purple-400 group-hover:before:w-full before:transition-all before:duration-500 before:ease-in-out before:-z-10 after:absolute after:bottom-0 after:right-0 after:w-6 after:h-1/2 after:bg-purple-400 group-hover:after:w-full after:transition-all after:duration-500 after:ease-in-out after:-z-10 inline-block z-0 group-hover:bg-lime-50 overflow-hidden text-white': {},
        },
        //portfolio
        '.portfolio-btn': {
            '@apply relative rounded-none after:absolute after:top-0 after:left-0 after:w-full after:h-full after:scale-0 hover:after:scale-100 after:transition-all font-medium z-0 after:-z-10 after:duration-300  after:ease-in-out': {},
        },
        '.photography-btn': {
            '@apply relative rounded-none after:absolute after:top-1/2 after:left-1/2 after:transform after:-translate-x-1/2 after:-translate-y-1/2 after:w-[92%] after:h-[80%] after:scale-100 hover:after:scale-0 after:transition-all font-medium z-0 after:-z-10 after:duration-300  after:ease-in-out': {},
        },
        // spa salon 
        '.spa-salon-btn': {
            '@apply relative after:absolute after:w-full after:h-px after:bg-white after:-bottom-4 after:left-0 after:scale-0 hover:after:scale-100 after:transition-all after:duration-700 after:ease-in-out  before:absolute before:-bottom-2 before:-right-2 before:w-4 before:h-4 before:bg-white before:rounded-full before:scale-100 hover:before:scale-0 before:transition-all before:duration-500 before:ease-in-out': {},
        },
        //travel
        '.travel-btn': {
            '@apply font-oswald text-sm overflow-hidden uppercase border border-white px-4 py-2 hover:skew-x-6 transition-all duration-700 ease-in-out relative z-20 text-black after:absolute after:top-0 after:left-0 after:w-full after:h-full after:bg-cyan-400 after:-skew-x-12 after:-z-10 after:transition-all after:duration-700 after:ease-in-out': {},
        },
        '.travel-light-btn': {
            '@apply font-oswald border-black after:bg-cyan-950 text-white text-xl overflow-hidden uppercase border dark:border-white px-4 py-2 hover:skew-x-6 transition-all duration-700 ease-in-out relative z-20 dark:text-black after:absolute after:top-0 after:left-0 after:w-full after:h-full dark:after:bg-cyan-400 after:-skew-x-12 after:-z-10 after:transition-all after:duration-700 after:ease-in-out': {},
        },
        // gym  
        '.gym-dark-btn': {
            '@apply font-gowun inline-block uppercase font-bold text-sm tracking-widest py-3 px-4 bg-transparent text-white relative z-20 after:absolute after:top-0 after:left-0 after:w-full after:h-full after:bg-red-800 after:-z-10 after:skew-x-12 hover:after:-skew-x-12 after:transition-all after:duration-700 after:ease-in-out before:absolute before:w-full before:h-full before:top-2 before:left-4 hover:before:left-2 before:bg-white before:-z-10 before:-skew-x-12': {},
        },
        '.gym-light-btn': {
            '@apply font-gowun inline-block uppercase font-bold text-sm tracking-widest py-3 px-4 bg-transparent text-white relative z-20 after:absolute after:top-0 after:left-0 after:w-full after:h-full after:bg-red-800 after:-z-10 after:skew-x-12 hover:after:-skew-x-12 after:transition-all after:duration-700 after:ease-in-out before:absolute before:w-full before:h-full before:top-2 before:left-4 hover:before:left-2 before:bg-black before:-z-10 before:-skew-x-12': {},
        },
        // charity 
        '.charity-dark-btn': {
            '@apply inline-block bg-gradient-to-r from-lime-600 to-green-700 hover:from-green-700 hover:to-lime-600 transition-all duration-700 ease-out relative after:w-3 after:h-3 after:rotate-[45deg] after:bg-white after:absolute after:top-1/2 after:-translate-y-1/2 after:-left-1.5 hover:after:scale-125 after:transition-all border-b-2 border-transparent hover:border-white hover:rotate-3 after:duration-700 after:ease-in-out  dark:from-lime-700 dark:to-green-800 mx-2 text-white py-3 px-6': {},

        },
        '.charity-btn': {
            '@apply inline-block mx-2 border border-white text-white py-2 lg:py-3 px-4 lg:px-6 hover:rotate-3 transition-all duration-700 ease-out relative after:w-3 after:h-3 after:rotate-[45deg] after:bg-white after:absolute after:top-1/2 after:-translate-y-1/2 after:-left-1.5 hover:after:scale-125 after:transition-all after:duration-700 after:ease-in-out': {},
        },

        // yoga & meditation 
        '.yoga-btn': {
            '@apply bg-gradient-to-tr from-purple-800 to-pink-700 dark:bg-pink-500 text-white px-6 py-3 my-6 text-sm capitalize hover:-hue-rotate-60 transition-all duration-300 ease-in-out inline-block relative': {},
        },

        // cryptocurrency 
        '.crypto-btn': {
            '@apply bg-lime-400  px-6 py-3 text-sm  transition-all duration-300 ease-in-out inline-block relative after:absolute after:bg-black  after:-top-1 after:-right-1 after:w-4 after:h-4 overflow-hidden hover:after:scale-150 hover:after:w-28 hover:after:h-28 after:transition-all after:duration-500 after:ease-in-out after:rounded-full z-20 after:-z-10 hover:text-white dark:after:bg-white dark:hover:text-black text-black': {},
        },
        //  fashion 
        '.fashion-btn': {
            '@apply bg-cyan-700 dark:bg-teal-700 text-white px-7 py-4 text-sm transition-all duration-300 ease-in-out inline-block relative z-20 dark:hover:text-black overflow-hidden after:absolute after:bg-black dark:after:bg-white after:w-1/2 after:h-0 after:top-0 after:left-0 hover:after:h-full after:transition-all after:duration-500 after:ease-in-out after:-z-10 before:absolute before:bg-black dark:before:bg-white before:w-1/2 before:h-0 before:bottom-0 before:right-0 hover:before:h-full before:transition-all before:duration-500 before:ease-in-out before:-z-10 hover:shadow-2xl': {},
        },
        //  decor 
        '.decor-btn': {
            '@apply bg-black dark:bg-white font-mooli dark:text-black text-white px-4 lg:px-7 py-2 lg:py-4 text-sm transition-all duration-300 ease-in-out inline-block relative z-20 overflow-hidden': {},
        },
        // elder care 
        '.elder-btn': {
            '@apply bg-purple-400 text-white py-3 px-6 capitalize hover:rounded-tr-3xl transition-all duration-700 ease-in-out relative after:!-z-10 after:bg-purple-200 after:absolute after:top-0 after:right-0 after:w-full after:h-full hover:after:top-3 hover:after:right-3 after:transition-all after:duration-700 after:ease-in-out': {},
        },
        // barber 
        '.barber-btn': {
            '@apply bg-yellow-600 inline-block border border-transparent hover:border-yellow-600 hover:bg-transparent  text-white py-2 px-3 lg:py-3 lg:px-4 capitalize font-mooli relative after:absolute after:bg-white after:-top-2 rtl:after:-right-2 ltr:after:-left-2 after:w-4 after:h-4 after:rounded-full hover:after:top-8 lg:hover:after:top-10 hover:after:bg-yellow-600 after:transition-all after:duration-700 after:ease-in-out transition-all duration-300 ease-in-out before:absolute before:w-full before:h-full before:top-0 before:left-0 before:bg-white/15 before:scale-0 hover:before:scale-100 before:transition-all before:duration-300 before:ease-in-out': {},
        },
        // blogger 
        '.blogger-btn': {
            '@apply inline-block bg-black text-white dark:bg-white dark:text-black border border-black dark:border-white hover:bg-transparent dark:hover:bg-transparent hover:text-black dark:hover:text-white transition-all duration-300 ease-in-out py-3 px-6 capitalize tracking-wide relative after:absolute after:-bottom-3 after:left-0 after:w-0 after:h-px after:bg-black dark:after:bg-white  hover:after:w-1/2 after:transition-all after:duration-500 after:ease-in-out  before:absolute before:-bottom-3 before:right-0 before:w-0 before:h-px before:bg-black dark:before:bg-white  hover:before:w-1/2 before:transition-all before:duration-500 before:ease-in-out': {},
        },
        // magazine 
        '.magazine-btn': {
            '@apply inline-block relative font-bold after:absolute after:size-10 after:border after:border-black dark:after:border-white capitalize hover:tracking-wider transition-all duration-500 ease-in-out after:rounded-full after:top-0 after:left-0 px-4 py-2': {},
        },
        // lawyer 
        '.lawyer-btn': {
            '@apply inline-block capitalize relative py-2 lg:py-3 rtl:pe-4 lg:rtl:pe-6 lg:ltr:ps-6 ltr:ps-4 border border-black dark:border-white rounded-r-3xl hover:rounded-3xl transition-all duration-500 ease-in-out': {},
        },
        // startup 
        '.start-up-btn': {
            '@apply py-3 px-5 border border-white relative z-20 after:absolute after:w-full after:h-full after:top-0 after:left-0 after:bg-blue-300/20 after:backdrop-blur-lg after:scale-0 hover:after:scale-100 after:-z-10 after:transition-all after:duration-500 after:ease-in-out': {},
        },
        // green-energy 
        '.green-btn': {
            '@apply overflow-hidden capitalize bg-green-900 border border-green-900 py-3 px-5 inline-block hover:bg-yellow-600 hover:border-yellow-600 hover:text-white transition-all duration-500 ease-in-out': {},
        },
        // green-energy 
        '.freelancer-btn': {
            '@apply inline-block py-3 px-5 bg-gradient-to-r from-red-300 dark:from-red-700 to-pink-300 dark:to-pink-600 mt-6 capitalize rounded-tl-2xl hover:-hue-rotate-60': {},
        },
        // real-estate 
        '.real-estate-btn': {
            '@apply font-bold capitalize text-white bg-cyan-950 rounded-button py-2 lg:py-3 px-4 lg:px-5 inline-block dark:bg-[#c0cdd1] dark:text-cyan-950 relative after:absolute after:top-0 after:left-0 after:w-0 after:h-full after:bg-black/50 dark:after:bg-white/50 after:-z-10 z-20 hover:after:w-full after:transition-all after:duration-500 after:ease-in-out overflow-hidden': {},
        },
        // product-showcase
        '.product-btn': {
            '@apply inline-block py-2 px-4 md:px-5 text-sm md:text-base border border-black dark:border-white capitalize bg-black dark:bg-white text-white dark:text-black hover:bg-transparent dark:hover:bg-transparent hover:text-black dark:hover:text-white transition-all duration-500 ease-in-out font-mooli': {},
        },
        // branding
        '.branding-btn': {
            '@apply inline-block capitalize text-black bg-gradient-to-r from-lime-200 to-teal-400 py-2 lg:py-3 px-4 lg:px-6 rounded hover:rotate-2 transition-all duration-700 ease-in-out': {},
        },
    })

})
