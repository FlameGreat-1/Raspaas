/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Wishlist init js
*/

// Function to decrease quantity
function decreaseQuantity(inputId) {
    const input = document.getElementById(inputId);
    let value = parseInt(input.value);
    if (value > 1) {
        value--;
        input.value = value;
        updateTotal(inputId);
    }
}

// Function to increase quantity
function increaseQuantity(inputId) {
    const input = document.getElementById(inputId);
    let value = parseInt(input.value);
    value++;
    input.value = value;
    updateTotal(inputId);
}

// Function to update item total
function updateTotal(inputId) {
    const productId = inputId.split('-')[1];
    const quantity = parseInt(document.getElementById(inputId).value);

    let price;
    if (productId === '1') {
        price = 28.98;
    } else if (productId === '2') {
        price = 27.00;
    } else if (productId === '3') {
        price = 16.51;
    }

    const total = (price * quantity).toFixed(2);
    document.getElementById(`total-${productId}`).textContent = `$${total}`;

    calculateCartTotal();
}

// Function to remove item
function removeItem(productId) {
    const element = document.getElementById(productId);
    element.classList.add('fadeOut');

    // Add animation if needed
    setTimeout(() => {
        element.remove();
        calculateCartTotal();
    }, 300);
}

// Calculate cart total
function calculateCartTotal() {
    let total = 0;
    const totals = document.querySelectorAll('[id^="total-"]');

    totals.forEach(item => {
        const value = parseFloat(item.textContent.replace('$', ''));
        total += value;
    });

    document.getElementById('cart-total').textContent = `$${total.toFixed(2)}`;
}