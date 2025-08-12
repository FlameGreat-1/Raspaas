// /*
// Template Name: Urbix - Admin & Dashboard Template
// Author: Pixeleyez
// Website: https://pixeleyez.com/
// Contact: pixeleyez@gmail.com
// File: Order init js
// */

document.addEventListener("DOMContentLoaded", () => {

    var spark1 = {
        chart: {
            id: 'sparkline1',
            type: 'line',
            width: 100,
            sparkline: {
                enabled: true
            },
            group: 'sparklines1'
        },
        series: [{
            name: 'teal',
            data: [25, 66, 41, 59, 25, 44, 12, 80, 50, 60]
        }],
        stroke: {
            curve: 'smooth',
            width: 2,
        },
        markers: {
            size: 0
        },
        tooltip: {
            fixed: {
                enabled: true,
                position: 'right'
            },
            x: {
                show: false
            }
        },
        colors: ['#fff'], // Solid color applied
        fill: {
            type: 'gradient',
            gradient: {
                shade: 'dark',
                gradientToColors: ['#18a538'],
                shadeIntensity: 1,
                type: 'horizontal',
                opacityFrom: 1,
                opacityTo: 1,
                stops: [0, 100, 100, 100]
            },
        },
        xaxis: {
            crosshairs: {
                width: 1
            },
        }
    };

    var spark2 = {
        chart: {
            id: 'sparkline2',
            type: 'line',
            width: 100,
            sparkline: {
                enabled: true
            },
            group: 'sparklines2'
        },
        series: [{
            name: 'teal',
            data: [25, 66, 41, 59, 25, 44, 12, 36, 9, 21]
        }],
        stroke: {
            curve: 'smooth',
            width: 2,
        },
        markers: {
            size: 0
        },
        tooltip: {
            fixed: {
                enabled: true,
                position: 'right'
            },
            x: {
                show: false
            }
        },
        colors: ['#fff'], // Solid color applied
        fill: {
            type: 'gradient',
            gradient: {
                shade: 'dark',
                gradientToColors: ['#ffc107'],
                shadeIntensity: 1,
                type: 'horizontal',
                opacityFrom: 1,
                opacityTo: 1,
                stops: [0, 100, 100, 100]
            },
        },
        xaxis: {
            crosshairs: {
                width: 1
            },
        }
    };

    var spark3 = {
        chart: {
            id: 'sparkline3',
            type: 'line',
            width: 100,
            sparkline: {
                enabled: true
            },
            group: 'sparklines3'
        },
        series: [{
            name: 'teal',
            data: [47, 45, 74, 32, 56, 31, 90, 30, 45, 80]
        }],
        stroke: {
            curve: 'smooth',
            width: 2,
        },
        markers: {
            size: 0
        },
        tooltip: {
            fixed: {
                enabled: true,
                position: 'right'
            },
            x: {
                show: false
            }
        },
        colors: ['#fff'], // Solid color applied
        fill: {
            type: 'gradient',
            gradient: {
                shade: 'dark',
                gradientToColors: ['#dc3545'],
                shadeIntensity: 1,
                type: 'horizontal',
                opacityFrom: 1,
                opacityTo: 1,
                stops: [0, 100, 100, 100]
            },
        },
        xaxis: {
            crosshairs: {
                width: 1
            },
        }
    };

    var spark4 = {
        chart: {
            id: 'sparkline4',
            type: 'line',
            width: 100,
            sparkline: {
                enabled: true
            },
            group: 'sparklines4'
        },
        series: [{
            name: 'teal',
            data: [47, 45, 74, 32, 56, 31, 50, 33, 90, 80]
        }],
        stroke: {
            curve: 'smooth',
            width: 2,
        },
        markers: {
            size: 0
        },
        tooltip: {
            fixed: {
                enabled: true,
                position: 'right'
            },
            x: {
                show: false
            }
        },
        colors: ['#fff'], // Solid color applied
        fill: {
            type: 'gradient',
            gradient: {
                shade: 'dark',
                gradientToColors: ['#18a538'],
                shadeIntensity: 1,
                type: 'horizontal',
                opacityFrom: 1,
                opacityTo: 1,
                stops: [0, 100, 100, 100]
            },
        },
        xaxis: {
            crosshairs: {
                width: 1
            },
        }
    };

    new ApexCharts(document.querySelector("#spark1"), spark1).render();
    new ApexCharts(document.querySelector("#spark2"), spark2).render();
    new ApexCharts(document.querySelector("#spark3"), spark3).render();
    new ApexCharts(document.querySelector("#spark4"), spark4).render();
});