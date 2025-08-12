/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Teacher Schedule init js
*/

document.addEventListener('DOMContentLoaded', function () {
    let teacherSelectChoice = document.getElementById('teacherSelect');
    if (teacherSelectChoice) {
        const choices = new Choices('#teacherSelect', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let subjectSelectChoice = document.getElementById('subjectSelect');
    if (subjectSelectChoice) {
        const choices = new Choices('#subjectSelect', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let daySelectChoice = document.getElementById('daySelect');
    if (daySelectChoice) {
        const choices = new Choices('#daySelect', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let roomSelectChoice = document.getElementById('roomSelect');
    if (roomSelectChoice) {
        const choices = new Choices('#roomSelect', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let classSelectChoice = document.getElementById('classSelect');
    if (classSelectChoice) {
        const choices = new Choices('#classSelect', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
});