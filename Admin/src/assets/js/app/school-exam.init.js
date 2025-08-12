/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: School Exam init js
*/

document.addEventListener('DOMContentLoaded', function () {
    let examStatus = document.getElementById('examStatus');
    if (examStatus) {
        const choicesstatus = new Choices('#examStatus', {
            placeholderValue: 'Select Status',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
});