/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Checkout init js
*/

document.addEventListener('DOMContentLoaded', function () {
    let productsizeChoice = document.getElementById('product-size-add');
    if (productsizeChoice) {
        const choices = new Choices('#product-size-add', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let productbrandChoice = document.getElementById('product-brand');
    if (productbrandChoice) {
        const choices = new Choices('#product-brand', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let productcategoryChoice = document.getElementById('product-category');
    if (productcategoryChoice) {
        const choices = new Choices('#product-category', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let productcolorChoice = document.getElementById('product-color');
    if (productcolorChoice) {
        const choices = new Choices('#product-color', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let customergenderChoice = document.getElementById('customer-gender');
    if (customergenderChoice) {
        const choices = new Choices('#customer-gender', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let productvisibilityChoice = document.getElementById('product-visibility');
    if (productvisibilityChoice) {
        const choices = new Choices('#product-visibility', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
});