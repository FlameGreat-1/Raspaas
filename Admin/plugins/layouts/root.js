const plugin = require('tailwindcss/plugin');
const generateColorStyles = require('./generateColorStyles');
const darkColors = require('./darkColors');

module.exports = plugin(function ({ addComponents }) {
    const darkThemes = Object.fromEntries(
        Object.keys(darkColors).map(key => [
            `.dark.${key}`,
            generateColorStyles(darkColors[key], 'dark')
        ])
    );
    addComponents({
        ...darkThemes,
    });
});