const plugin = require('tailwindcss/plugin');

module.exports = plugin(function ({ addComponents }) {
    addComponents({
        '.card': {
            // Styles for the main card component
            '@apply rounded-md border border-gray-200 mb-5 shadow-lg shadow-gray-100 bg-white': {},
        },

        '.card-body': {
            // Styles for the card body
            '@apply p-5': {},
        },

        '.card-header': {
            // Styles for the card header
            '@apply p-5 border-b border-gray-200 rounded-t-md': {},
        },

        '.card-footer': {
            // Styles for the card footer
            '@apply p-5 border-t border-gray-200 rounded-b-md': {},
        }
    });
});
