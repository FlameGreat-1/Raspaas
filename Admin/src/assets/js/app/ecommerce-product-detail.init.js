/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Email init js
*/ 
 
 // Product detail layout 01 swiper
 var productSmall = new Swiper(".product-small", {
    spaceBetween: 0,
    slidesPerView: 6,
    direction: "horizontal",
    breakpoints: {
        100: {
            direction: "horizontal",
            slidesPerView: 4,
        },
        1200: {
            direction: "horizontal",

        }
    },
});
var productMain = new Swiper(".product-main", {
    slidesPerView: 1,
    spaceBetween: 40,
    direction: 'horizontal',
    autoHeight: true,
    navigation: {
        nextEl: ".swiper-button-next",
        prevEl: ".swiper-button-prev",
    },
    thumbs: {
        swiper: productSmall,
    },
});

var productMain = new Swiper(".swiper-reviews", {
    slidesPerView: 1,
    spaceBetween: 10,
    navigation: {
        nextEl: ".swiper-button-next",
        prevEl: ".swiper-button-prev",
    },
});

