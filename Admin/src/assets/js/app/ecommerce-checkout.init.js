/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Checkout init js
*/

document.addEventListener('DOMContentLoaded', function () {
    // Address options selection
    const addressOptions = document.querySelectorAll('.address-option');
    addressOptions.forEach(option => {
        option.addEventListener('click', function () {
            const radio = this.querySelector('.address-option-radio');
            radio.checked = true;

            addressOptions.forEach(opt => {
                opt.classList.remove('selected');
            });
            this.classList.add('selected');
        });
    });

    // Payment options selection
    const paymentOptions = document.querySelectorAll('.payment-option');
    paymentOptions.forEach(option => {
        option.addEventListener('click', function () {
            const radio = this.querySelector('.payment-option-radio');
            radio.checked = true;

            paymentOptions.forEach(opt => {
                opt.classList.remove('selected');
            });
            this.classList.add('selected');

            // Show/hide card details form based on selection
            const cardDetailsForm = document.getElementById('cardDetailsForm');
            if (radio.id === 'creditCard') {
                cardDetailsForm.style.display = 'block';
            } else {
                cardDetailsForm.style.display = 'none';
            }
        });
    });

    // Address type selection
    const typeOptions = document.querySelectorAll('.type-option');
    typeOptions.forEach(option => {
        option.addEventListener('click', function () {
            typeOptions.forEach(opt => {
                opt.classList.remove('selected');
            });
            this.classList.add('selected');
        });
    });

    // Show/hide new address form
    const showFormBtn = document.getElementById('showAddressForm');
    const newAddressForm = document.getElementById('newAddressForm');
    const cancelFormBtn = document.getElementById('cancelAddressForm');

    showFormBtn.addEventListener('click', function () {
        newAddressForm.style.display = 'block';
        showFormBtn.style.display = 'none';
    });

    cancelFormBtn.addEventListener('click', function () {
        newAddressForm.style.display = 'none';
        showFormBtn.style.display = 'flex';
    });

    // Multi-step navigation
    const stepContents = document.querySelectorAll('.step-content');
    const steps = document.querySelectorAll('.step');

    function goToStep(stepNumber) {
        stepContents.forEach(content => {
            content.classList.remove('active');
        });
        steps.forEach(step => {
            step.classList.remove('active');
            step.classList.remove('completed');

            const dataStep = parseInt(step.getAttribute('data-step'));
            if (dataStep < stepNumber) {
                step.classList.add('completed');
            } else if (dataStep === stepNumber) {
                step.classList.add('active');
            }
        });
        document.getElementById('step-' + stepNumber).classList.add('active');
    }

    document.getElementById('toStep2').addEventListener('click', function () {
        goToStep(2);
    });

    document.getElementById('toStep1').addEventListener('click', function () {
        goToStep(1);
    });

    document.getElementById('toStep3').addEventListener('click', function () {
        goToStep(3);
    });
});