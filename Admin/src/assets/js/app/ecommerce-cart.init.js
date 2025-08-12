/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Cart init js
*/

// function to update total price
function updateTotal(inputId) {
    const input = document.getElementById(inputId);
    const price = parseFloat(input.getAttribute('data-price'));
    const quantity = parseInt(input.value);
    const total = price * quantity;
    const totalElement = document.getElementById('total_' + inputId);
    totalElement.textContent = total.toFixed(2);
}

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

document.addEventListener('DOMContentLoaded', function () {
    // Toggle items collapse
    const toggleButton = document.getElementById('toggleItems');
    const itemsCollapse = document.getElementById('itemsCollapse');

    toggleButton.addEventListener('click', function () {
        if (itemsCollapse.classList.contains('show')) {
            itemsCollapse.classList.remove('show');
            toggleButton.querySelector('i').classList.remove('fa-chevron-down');
            toggleButton.querySelector('i').classList.add('fa-chevron-up');
        } else {
            itemsCollapse.classList.add('show');
            toggleButton.querySelector('i').classList.remove('fa-chevron-up');
            toggleButton.querySelector('i').classList.add('fa-chevron-down');
        }
    });

    // Quantity increase buttons
    document.querySelectorAll('.increase-btn').forEach(button => {
        button.addEventListener('click', function () {
            const inputId = this.getAttribute('data-input');
            const input = document.getElementById(inputId);
            input.value = parseInt(input.value) + 1;
            updateCartTotals();
        });
    });

    // Quantity decrease buttons
    document.querySelectorAll('.decrease-btn').forEach(button => {
        button.addEventListener('click', function () {
            const inputId = this.getAttribute('data-input');
            const input = document.getElementById(inputId);
            if (parseInt(input.value) > 1) {
                input.value = parseInt(input.value) - 1;
                updateCartTotals();
            }
        });
    });

    // Remove item functionality
    document.querySelectorAll('.remove-btn').forEach(button => {
        button.addEventListener('click', function () {
            const productCard = this.closest('.product-card');
            productCard.style.opacity = '0.5';
            setTimeout(() => {
                productCard.remove();
                updateCartCounter();
                updateCartTotals();
            }, 300);
        });
    });

    // Update cart counter
    function updateCartCounter() {
        const itemCount = document.querySelectorAll('.product-card').length;
        document.querySelector('.cart-header h2 span').textContent = `(${itemCount} items)`;
    }

    // Update cart totals
    function updateCartTotals() {
        // For demo purposes - in a real app this would calculate actual totals
        console.log("Cart totals would update here");
    }
});