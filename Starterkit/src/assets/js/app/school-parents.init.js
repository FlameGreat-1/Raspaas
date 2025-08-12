/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: School Parents init js
*/

document.addEventListener('DOMContentLoaded', function () {
    let parentsGender = document.getElementById('parentsGender');
    if (parentsGender) {
        const choicesstatus = new Choices('#parentsGender', {
            placeholderValue: 'Select Status',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
});