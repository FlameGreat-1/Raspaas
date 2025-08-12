/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Blog List init js
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
          slidesPerView: 5,
          spaceBetween: 20,
        }
      },
});