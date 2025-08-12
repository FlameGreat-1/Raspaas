/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: School Course init js
*/

document.addEventListener('DOMContentLoaded', function () {
    let courseStatus = document.getElementById('courseStatus');
    if (courseStatus) {
        const choicesstatus = new Choices('#courseStatus', {
            placeholderValue: 'Select Status',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
});