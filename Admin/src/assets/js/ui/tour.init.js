/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Tour init js
*/

import Shepherd from '../../libs/shepherd.js/esm/shepherd.mjs';

document.addEventListener('DOMContentLoaded', function () {
    const tour = new Shepherd.Tour({
        useModalOverlay: true,
        defaultStepOptions: {
            cancelIcon: { enabled: true },
            classes: 'shepherd-theme-arrows',
            scrollTo: { behavior: 'smooth', block: 'center' },
            classPrefix: 'my-tour-'
        }
    });

    tour.addStep({
        id: 'start-tour',
        text: 'Welcome to Urbix! This template offers advanced features for your admin dashboard.',
        attachTo: { element: 'test', on: 'bottom' },
        buttons: [{ text: 'Next', action: tour.next }]
    });

    tour.addStep({
        id: 'project-management',
        text: 'This section provides tools for effective project management.',
        attachTo: { element: '.row > div:nth-child(1) i', on: 'bottom' },
        buttons: [
            { text: 'Back', action: tour.back },
            { text: 'Next', action: tour.next }
        ]
    });

    tour.addStep({
        id: 'task-automation',
        text: 'Here, you can streamline your workflow with automation solutions.',
        attachTo: { element: '.row > div:nth-child(2) i', on: 'bottom' },
        buttons: [
            { text: 'Back', action: tour.back },
            { text: 'Next', action: tour.next }
        ]
    });

    tour.addStep({
        id: 'data-analysis',
        text: 'This section helps you turn data into actionable insights.',
        attachTo: { element: '.row > div:nth-child(3) i', on: 'bottom' },
        buttons: [
            { text: 'Back', action: tour.back },
            { text: 'Next', action: tour.next }
        ]
    });

    tour.addStep({
        id: 'who-we-are',
        text: 'Learn more about us and our commitment to excellence.',
        attachTo: { element: 'h4:nth-of-type(2)', on: 'bottom' },
        buttons: [
            { text: 'Back', action: tour.back },
            { text: 'Finish', action: tour.complete }
        ]
    });
    
    // Automatically start the tour when the page loads
    tour.start();
});