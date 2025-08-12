/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Media init js
*/

function renderCharts() {
    // Engagement
    var options = {
        series: [{
            name: 'Website Blog',
            type: 'column',
            data: [440, 505, 414, 671, 227, 413, 201, 352, 752, 320, 257, 160]
        }, {
            name: 'Social Media',
            type: 'line',
            data: [223, 642, 335, 727, 343, 152, 417, 300, 322, 22, 100, 20]
        }],
        chart: {
            height: 328,
            type: 'line',
            toolbar: {
                show: false
            }
        },
        colors: ['#5b66eb', '#18a538'],
        legend: {
            show: false
        },
        stroke: {
            width: [0, 4]
        },
        dataLabels: {
            enabled: true,
            enabledOnSeries: [1]
        },
        labels: ['01 Jan', '02 Jan', '03 Jan', '04 Jan', '05 Jan', '06 Jan', '07 Jan', '08 Jan', '09 Jan', '10 Jan', '11 Jan', '12 Jan'],
        yaxis: [{
            title: {
                text: '',
            },
        },
        {
            opposite: true,
            title: {
                text: ''
            }
        }]
    };

    var chart = new ApexCharts(document.querySelector("#engagement"), options);
    chart.render();

    // spark
    var spark1 = {
        chart: {
            id: 'sparkline1',
            type: 'line',
            height: 60,
            sparkline: {
                enabled: true
            },
            group: 'sparklines1'
        },
        series: [{
            name: 'teal',
            data: [2, 0, 5, 7, 6, 8, 9]
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
        colors: ['#18a538'], // Solid color applied
        fill: {
            opacity: 1 // No gradient, just solid fill
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
            height: 60,
            sparkline: {
                enabled: true
            },
            group: 'sparklines2'
        },
        series: [{
            name: 'teal',
            data: [8, 0, 8, 0]
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
        colors: ['#dc3545'], // Solid color applied
        fill: {
            opacity: 1 // No gradient, just solid fill
        },
        xaxis: {
            crosshairs: {
                width: 1
            },
        }
    };
    new ApexCharts(document.querySelector("#spark1"), spark1).render();
    new ApexCharts(document.querySelector("#spark2"), spark2).render();

    // visitors
    var options = {
        chart: {
            type: 'bar',
            height: 320,
            stacked: true,
            toolbar: {
                show: false
            }
        },
        series: [
            {
                name: 'Segment A',
                data: [1000, 900, 800, 1200, 2000, 1000, 1000]
            },
            {
                name: 'Segment B',
                data: [1200, 2000, 1000, 1000, 2500, 1000, 1000]
            },
            {
                name: 'Segment C',
                data: [800, 1000, 700, 1300, 1000, 1000, 1100]
            }
        ],
        xaxis: {
            categories: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        },
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '40%',
                borderRadius: 12,
                borderRadiusWhenStacked: 'all', // Makes all parts rounded
                borderRadiusApplication: 'around' // Helps make both ends round (best effort)
            }
        },
        stroke: {
            show: true,
            width: 2,
            colors: ['#fff'] // Creates space between parts
        },
        colors: ['#5b66eb', '#6e78e7', '#959be7'],
        legend: {
            show: false
        }
    };

    var chart = new ApexCharts(document.querySelector("#visitors"), options);
    chart.render();


    // reached
    var options = {
        series: [{
            name: 'Security',
            data: [44, 55, 41, 67, 22, 43]
        }],
        chart: {
            type: 'bar',
            height: 100,
            stacked: true,
            toolbar: {
                show: false
            },
            zoom: {
                enabled: true
            }
        },
        colors: ['#5b66eb'],
        dataLabels: {
            enabled: false
        },
        responsive: [{
            breakpoint: 480,
            options: {
                legend: {
                    position: 'bottom',
                    offsetX: -10,
                    offsetY: 0
                }
            }
        }],
        plotOptions: {
            bar: {
                borderRadius: 3,
                horizontal: false,
                columnWidth: '55%',
                dataLabels: {
                    total: {
                        enabled: false,
                        style: {
                            fontSize: '13px',
                            fontWeight: 900
                        }
                    }
                }
            },
        },
        grid: {
            xaxis: {
                lines: {
                    show: false
                }
            },
            yaxis: {
                lines: {
                    show: false
                }
            }
        },
        xaxis: {
            axisBorder: {
                show: false,
            },
            axisTicks: {
                show: false,
            },
            labels: {
                show: false,
            }
        },
        yaxis: {
            axisBorder: {
                show: false,
            },
            axisTicks: {
                show: false,
            },
            labels: {
                show: false,
            }
        },
        legend: {
            position: 'right',
            offsetY: 40
        },
        fill: {
            opacity: 1
        }
    };

    var chart = new ApexCharts(document.querySelector("#reached"), options);
    chart.render();

    // Followers
    var options = {
        series: [{
            name: 'Security',
            data: [44, 55, 41, 67, 22, 43]
        }],
        chart: {
            type: 'bar',
            height: 100,
            stacked: true,
            toolbar: {
                show: false
            },
            zoom: {
                enabled: true
            }
        },
        colors: ['#5b66eb'],
        dataLabels: {
            enabled: false
        },
        responsive: [{
            breakpoint: 480,
            options: {
                legend: {
                    position: 'bottom',
                    offsetX: -10,
                    offsetY: 0
                }
            }
        }],
        plotOptions: {
            bar: {
                borderRadius: 3,
                horizontal: false,
                columnWidth: '55%',
                dataLabels: {
                    total: {
                        enabled: false,
                        style: {
                            fontSize: '13px',
                            fontWeight: 900
                        }
                    }
                }
            },
        },
        grid: {
            xaxis: {
                lines: {
                    show: false
                }
            },
            yaxis: {
                lines: {
                    show: false
                }
            }
        },
        xaxis: {
            axisBorder: {
                show: false,
            },
            axisTicks: {
                show: false,
            },
            labels: {
                show: false,
            }
        },
        yaxis: {
            axisBorder: {
                show: false,
            },
            axisTicks: {
                show: false,
            },
            labels: {
                show: false,
            }
        },
        legend: {
            position: 'right',
            offsetY: 40
        },
        fill: {
            opacity: 1
        }
    };

    var chart = new ApexCharts(document.querySelector("#followers"), options);
    chart.render();

    // vectormap
    var worldemapmarkers = new jsVectorMap({
        selector: "#world-map", // Use the correct selector
        map: 'world',
        zoomOnScroll: false,
        selectedMarkers: [0, 2], // Select specific markers (index-based)
        regionStyle: {
            initial: {
                stroke: "#9599ad",
                strokeWidth: 0.25,
                fillOpacity: 1,
            },
        },
        markersSelectable: true,
        markers: [
            { coords: [65.524, 70.3188] },
            { coords: [10.524, 78.3188] },
            { coords: [50.1304, -80.3468] },
            { coords: [-40.524, 140.3188] },
        ],
        markerStyle: {
            initial: {
                fill: "#7699BB" // Default marker color
            },
            selected: { fill: "var(--bs-primary)" },
            hover: { fill: "var(--bs-primary)" },
        },
        labels: {
            markers: {
                render: function (marker) {
                    return marker.name; // Render the marker name
                }
            }
        }
    });

    //Segmentation
    var options = {
        series: [{
            name: 'Net Profit',
            data: [44, 55, 57, 56, 61, 58]
        }, {
            name: 'Revenue',
            data: [76, 85, 101, 98, 87, 105]
        }],
        chart: {
            type: 'bar',
            height: 294,
            toolbar: {
                show: false
            }
        },
        plotOptions: {
            bar: {
                horizontal: false,
                columnWidth: '55%',
                borderRadius: 5,
                borderRadiusApplication: 'end'
            },
        },
        dataLabels: {
            enabled: false
        },
        stroke: {
            show: true,
            width: 2,
            colors: ['transparent']
        },
        grid: {
            xaxis: {
                lines: {
                    show: false
                }
            },
            yaxis: {
                lines: {
                    show: false
                }
            }
        },
        xaxis: {
            axisBorder: {
                show: false,
            },
            axisTicks: {
                show: false,
            },
            categories: ['0-12', '13-17', '18-24', '25-34', '35-44', '45-60'],
        },
        yaxis: {
            axisBorder: {
                show: false,
            },
            axisTicks: {
                show: false,
            },
            labels: {
                show: false,
            }
        },
        colors: ['#d6d9fa', '#5b66eb'],
        fill: {
            opacity: 1
        },
        legend: {
            show: false
        },
        tooltip: {
            y: {
                formatter: function (val) {
                    return "$ " + val + " thousands"
                }
            }
        }
    };

    var chart = new ApexCharts(document.querySelector("#segmentation "), options);
    chart.render();

    // DonutChart
    var options = {
        series: [70, 30],
        chart: {
            type: 'donut',
            height: 205,
        },
        labels: ['Male', 'Female'],
        colors: ['#5b66eb', '#d6d9fa'],
        legend: {
            show: false
        },
        dataLabels: {
            enabled: false // disable default data labels
        },
        plotOptions: {
            pie: {
                donut: {
                    size: '30%'
                }
            }
        }
    };

    var chart = new ApexCharts(document.querySelector("#donutChart"), options);
    chart.render();

    function generateData(count, yrange) {
        var i = 0;
        var series = [];
        while (i < count) {
            var x = 'w' + (i + 1).toString();
            var y = Math.floor(Math.random() * (yrange.max - yrange.min + 1)) + yrange.min;

            series.push({
                x: x,
                y: y
            });
            i++;
        }
        return series;
    }

    //Global
    var options = {
        series: [{
            name: 'Sun',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        },
        {
            name: 'Mon',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        },
        {
            name: 'Tue',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        },
        {
            name: 'Wed',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        },
        {
            name: 'Thu',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        },
        {
            name: 'Fri',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        },
        {
            name: 'Sat',
            data: generateData(5, {
                min: 0,
                max: 90
            })
        }
        ],
        chart: {
            height: 360,
            type: 'heatmap',
            toolbar: {
                show: false
            }
        },
        dataLabels: {
            enabled: false
        },
        colors: ["#5b66eb"],
    };

    var chart = new ApexCharts(document.querySelector("#global"), options);
    chart.render();
}

setTimeout(() => {
    renderCharts();
}, 250);

// Post Activity
// Define the data structure for the calendar
const calendarData = [
    // Week 1
    2, 9, 35, 9, 9, 9, 2,
    // Week 2
    1, 9, 35, 35, 35, 9, 35,
    // Week 3
    9, 35, 9, 9, 35, 35, 9,
    // Week 4 (partial)
    35, 9, 35, 3, 9
];

const grid = document.getElementById('calendar-grid');

// Populate the calendar grid
calendarData.forEach(value => {
    const day = document.createElement('div');
    day.className = `calendar-day value-${value}`;
    day.textContent = value;
    grid.appendChild(day);
});

// Add event listeners
document.querySelectorAll('.calendar-day').forEach(day => {
    day.addEventListener('click', () => {
        alert(`You clicked on value: ${day.textContent}`);
    });
});