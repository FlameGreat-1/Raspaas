/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Apps Email init js
*/

const emailDetails = document.getElementById('emailDetails');
const emailList = document.getElementById('emailList');
const closeReadEmail = document.getElementById('closeReadEmail');
const emailSidebar = document.getElementById('email-sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');

closeReadEmail?.addEventListener('click', function () {
    emailList.classList.remove('d-none');
    emailDetails.classList.add('d-none');
});

emailList?.querySelectorAll('#mail-list li').forEach((item) => {
    item.addEventListener('click', function () {
        emailList.classList.add('d-none');
        emailDetails.classList.remove('d-none');
    });
});

if (document.getElementById('snowEditor')) {
    new Quill('#snowEditor', {
        theme: 'snow',
        modules: {
            toolbar: true,
        },
        placeholder: 'Compose your content here...',
    });
}

document.getElementById('backdrop-overlay-email')?.addEventListener('click', function (e) {
    e.preventDefault();
    emailSidebar.classList.remove('active');
});

sidebarToggle?.addEventListener('click', function () {
    emailSidebar.classList.add('active');
});

window.addEventListener("resize", () => {
    emailSidebar.classList.remove("active");
});

if(window.innerWidth <= 1199) {
    emailSidebar.classList.remove("active");
}