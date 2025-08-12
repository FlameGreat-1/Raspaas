/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Order init js
*/

// Status modal
const updateStatusBtn = document.getElementById('updateStatus');
const statusModal = new bootstrap.Modal(document.getElementById('statusModal'));

updateStatusBtn.addEventListener('click', function () {
    statusModal.show();
});

// Status change from sidebar
const saveStatusBtn = document.getElementById('saveStatus');
saveStatusBtn.addEventListener('click', function () {
    const selectedStatus = document.getElementById('statusSelect').value;
    alert(`Order status updated to: ${selectedStatus}`);
});

// Status change from modal
const confirmStatusUpdateBtn = document.getElementById('confirmStatusUpdate');
confirmStatusUpdateBtn.addEventListener('click', function () {
    const selectedStatus = document.getElementById('modalStatusSelect').value;
    const notifyCustomer = document.getElementById('notifyCustomer').checked;

    let message = `Order status updated to: ${selectedStatus}`;
    if (notifyCustomer) {
        message += "\nCustomer has been notified via email.";
    }

    alert(message);
    statusModal.hide();

    // Add new status to timeline
    addStatusToTimeline(selectedStatus);
});