/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Admission Form init js
*/

document.addEventListener('DOMContentLoaded', function () {
    let genderChoice = document.getElementById('gender-choice');
    if (genderChoice) {
        const choices = new Choices('#gender-choice', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let gradeChoice = document.getElementById('grade-choice');
    if (gradeChoice) {
        const choices = new Choices('#grade-choice', {
            placeholderValue: 'Select options',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let academicYearsChoice = document.getElementById('academicYears');
    if (academicYearsChoice) {
        const choices = new Choices('#academicYears', {
            placeholderValue: 'Select Academic Years',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let statusChoice = document.getElementById('status');
    if (statusChoice) {
        const choices = new Choices('#status', {
            placeholderValue: 'Select Status',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let gradeLevelsChoice = document.getElementById('gradeLevels');
    if (gradeLevelsChoice) {
        const choices = new Choices('#gradeLevels', {
            placeholderValue: 'Select Grade Levels',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
    let paymentStatusChoice = document.getElementById('paymentStatus');
    if (paymentStatusChoice) {
        const choices = new Choices('#paymentStatus', {
            placeholderValue: 'Select Payment Status',
            searchPlaceholderValue: 'Search...',
            removeItemButton: true,
            itemSelectText: 'Press to select',
        });
    }
});
const localeEn = {
    days: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
    daysShort: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    daysMin: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
    months: ['January','February','March','April','May','June', 'July','August','September','October','November','December'],
    monthsShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
    today: 'Today',
    clear: 'Clear',
    dateFormat: 'mm/dd/yyyy',
    timeFormat: 'hh:ii aa',
    firstDay: 0
}
new AirDatepicker('#dob', {
    autoClose: false,
  dateFormat: 'dd/MM/yyyy',
  locale: localeEn,
});
