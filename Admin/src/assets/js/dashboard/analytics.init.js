/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: Analytics init js
*/

function renderCharts() {
  // level-chart
  var options = {
    series: [{
      name: 'Volume',
      data: [44, 55, 41, 67, 22, 43]
    }, {
      name: 'Service',
      data: [13, 23, 20, 8, 13, 27]
    }],
    dataLabels: {
      enabled: false
    },
    colors: ['#5b66eb', '#e9e9e9'],
    legend: {
      show: false
    },
    chart: {
      type: 'bar',
      height: 177,
      stacked: true,
      toolbar: {
        show: false
      },
      zoom: {
        enabled: true
      }
    },
    responsive: [{
      breakpoint: 480,
      options: {
        legend: {
          show: false
        }
      }
    }],
    plotOptions: {
      bar: {
        horizontal: false,
        borderRadius: 4,
        columnWidth: '35%',
        borderRadiusApplication: 'end', // 'around', 'end'
        borderRadiusWhenStacked: 'last', // 'all', 'last'
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
    xaxis: {
      labels: {
        formatter: function (value) {
          show: false
        }
      }
    },
    grid: {
      yaxis: {
        lines: {
          show: false
        }
      },
    },
    yaxis: {
      show: false
    },
    legend: {
      show: false
    },
    fill: {
      opacity: 1
    }
  };

  var chart = new ApexCharts(document.querySelector("#level-chart"), options);
  chart.render();

  // transaction
  var options = {
    series: [{
      name: 'Security',
      data: [44, 55, 41, 67, 22, 43, 20, 15, 35, 50, 26, 39]
    }],
    chart: {
      type: 'bar',
      height: 350,
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
        horizontal: false,
        columnWidth: '35%',
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
    xaxis: {
      categories: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nev', 'Dec',],
    },
    legend: {
      position: 'right',
      offsetY: 40
    },
    yaxis: {
      title: {
        text: 'Security rating'
      }
    },
    fill: {
      opacity: 1
    }
  };

  var chart = new ApexCharts(document.querySelector("#transaction"), options);
  chart.render();

  // overview
  var options = {
    series: [70],
    chart: {
      height: 295,
      type: 'radialBar',
    },
    colors: ['#5b66eb'],
    plotOptions: {
      radialBar: {
        hollow: {
          size: '70%',
        }
      },
    },
    labels: ['$500.45'],
  };

  var chart = new ApexCharts(document.querySelector("#overview"), options);
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

  // overall
  var options = {
    series: [{
      name: 'series1',
      data: [0, 60, 50, 65, 55, 75, 35, 70, 85, 65, 85, 85, 20, 90, 100]
    }],
    chart: {
      height: 252,
      type: 'area',
      toolbar: {
        show: false
      },
    },
    colors: ['#5b66eb'],
    dataLabels: {
      enabled: false
    },
    stroke: {
      curve: 'straight'
    },
    xaxis: {
      tooltip: {
        enabled: false
      }
    },
    tooltip: {
      x: {
        format: 'dd/MM/yy HH:mm'
      },
    },
  };

  var chart = new ApexCharts(document.querySelector("#overall"), options);
  chart.render();

  // Revenue
  var options = {
    series: [{
      name: 'Cash Flow',
      data: [1.45, 5.42, 5.9, -0.42, -12.6, -18.1, -18.2, -14.16, -11.1, -6.09, 0.34, 3.88, 13.07,
        5.8, 2, 7.37, 8.1, 13.57, 15.75, 17.1, 19.8, -27.03, -54.4, -47.2, -43.3, -18.6, -
        48.6, -41.1, -39.6, -37.6, -29.4, -21.4, -2.4
      ]
    }],
    chart: {
      type: 'bar',
      height: 336,
      toolbar: {
        show: false
      },
    },
    plotOptions: {
      bar: {
        colors: {
          ranges: [{
            from: -100,
            to: -46,
            color: '#5b66eb'
          }, {
            from: -45,
            to: 0,
            color: '#5b66eb'
          }]
        },
        columnWidth: '80%',
      }
    },
    dataLabels: {
      enabled: false,
    },
    yaxis: {
      labels: {
        formatter: function (y) {
          return y.toFixed(0) + "%";
        }
      }
    },
    xaxis: {
      type: 'datetime',
      categories: [
        '2011-01-01', '2011-02-01', '2011-03-01', '2011-04-01', '2011-05-01', '2011-06-01',
        '2011-07-01', '2011-08-01', '2011-09-01', '2011-10-01', '2011-11-01', '2011-12-01',
        '2012-01-01', '2012-02-01', '2012-03-01', '2012-04-01', '2012-05-01', '2012-06-01',
        '2012-07-01', '2012-08-01', '2012-09-01', '2012-10-01', '2012-11-01', '2012-12-01',
        '2013-01-01', '2013-02-01', '2013-03-01', '2013-04-01', '2013-05-01', '2013-06-01',
        '2013-07-01', '2013-08-01', '2013-09-01'
      ],
      labels: {
        rotate: -90
      }
    }
  };

  var chart = new ApexCharts(document.querySelector("#revenue"), options);
  chart.render();

  // spark1
  var spark1 = {
    chart: {
      id: 'sparkline1',
      type: 'line',
      height: 80,
      sparkline: {
        enabled: true
      },
      group: 'sparklines1'
    },
    series: [{
      name: 'teal',
      data: [0, 66, 41, 80, 31, 45, 35, 80, 45, 65, 55, 80, 79, 85, 60, 80, 75, 85]
    }],
    stroke: {
      curve: 'smooth',
      width: 4,
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
    colors: ['#5b66eb'], // Solid color applied
    fill: {
      type: 'gradient',
      gradient: {
        shade: 'dark',
        gradientToColors: ['#263238'],
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

}

setTimeout(() => {
  renderCharts();
}, 250);