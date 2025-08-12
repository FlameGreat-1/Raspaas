/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Profile init js
*/

var swiper = new Swiper(".default-swiper", {
    slidesPerView: 1,
    loop: true,
    spaceBetween: 20,
    autoplay: {
        delay: 1500,
        disableOnInteraction: false,
      },
      breakpoints: {
        768: {
          slidesPerView: 3,
          spaceBetween: 20,
        }
      },
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

new AirDatepicker('#basic-picker', {
    autoClose: false,
  dateFormat: 'dd/MM/yyyy',
  locale: localeEn,
});

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
  let languageChoice = document.getElementById('language-choice');
  if (languageChoice) {
      const choices = new Choices('#language-choice', {
          placeholderValue: 'Select options',
          searchPlaceholderValue: 'Search...',
          removeItemButton: true,
          itemSelectText: 'Press to select',
      });
  }
  let timezoneChoice = document.getElementById('timezone-choice');
  if (timezoneChoice) {
      const choices = new Choices('#timezone-choice', {
          placeholderValue: 'Select options',
          searchPlaceholderValue: 'Search...',
          removeItemButton: true,
          itemSelectText: 'Press to select',
      });
  }
});