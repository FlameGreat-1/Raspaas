/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: School init js
*/

// gridjs_expenses
if (document.getElementById("gridjs_expenses")) {
  new gridjs.Grid({
    columns: [
      { name: 'ID No', formatter: (cell) => gridjs.html(`<span class="text-muted">${cell}</span>`) },
      { name: 'Expense Type', formatter: (cell) => gridjs.html(`<span class="text-muted">${cell}</span>`) },
      { name: 'Amount', formatter: (cell) => gridjs.html(`<span class="text-muted">${cell}</span>`) },
      { name: 'Status', formatter: (cell) => gridjs.html(`<span class="text-muted">${cell}</span>`) },
      { name: 'E-mail', formatter: (cell) => gridjs.html(`<span class="text-muted">${cell}</span>`) },
      { name: 'Date', formatter: (cell) => gridjs.html(`<span class="text-muted">${cell}</span>`) }
    ],
    sort: true,
    data: [
      ["#3055", "Salary", "$300.00", "Due", "kazifahim93@gmail.com", "20/06/2017"],
      ["#3056", "Exam Fee", "$500.00", "Paid", "kazifahim93@gmail.com", "20/06/2017"],
      ["#3057", "Library Fee", "$500.00", "Paid", "kazifahim93@gmail.com", "20/06/2017"],
      ["#3058", "Class Test Fee", "$500.00", "Due", "kazifahim93@gmail.com", "20/06/2017"],
      ["#3059", "Meeting", "$600.00", "Paid", "kazifahim93@gmail.com", "20/06/2017"],
      ["#3060", "Extra Fee", "$700.00", "Paid", "kazifahim93@gmail.com", "20/06/2017"],
    ]
  }).render(document.getElementById("gridjs_expenses"));
}

// inline-picker
const localeEn = {
  days: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
  daysShort: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  daysMin: ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'],
  months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  monthsShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  today: 'Today',
  clear: 'Clear',
  dateFormat: 'mm/dd/yyyy',
  timeFormat: 'hh:ii aa',
  firstDay: 0
}
new AirDatepicker('#inline-picker', {
  inline: true,
  locale: localeEn,
})

function renderCharts() {
  // income
  var options = {
    chart: {
      type: 'line',
      height: 300,
      toolbar: {
        show: false
      }
    },
    series: [{
      name: 'Series A',
      data: [6000, 6800, 3000, 4300, 5000, 2800, 4700, 6000, 4500]
    }, {
      name: 'Series B',
      data: [4500, 5200, 1700, 3000, 3600, 2000, 3900, 4800, 3400]
    }],
    xaxis: {
      categories: ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'],
      labels: {
        style: {
          fontSize: '14px'
        }
      }
    },
    stroke: {
      curve: 'smooth',
      width: 3
    },
    colors: ['#5b66eb', '#775DD0'],
    markers: {
      size: 0
    },
    dataLabels: {
      enabled: false
    },
    yaxis: {
      labels: {
        formatter: function (val) {
          return val >= 1000 ? (val / 1000) + 'k' : val;
        }
      }
    },
    legend: {
      show: false,
    }
  };

  var chart = new ApexCharts(document.querySelector("#income"), options);
  chart.render();

  // attendanceChart
  var options = {
    series: [84, 91],
    chart: {
      height: 250,
      type: 'radialBar',
    },
    plotOptions: {
      radialBar: {
        hollow: {
          size: '40%',
        },
        dataLabels: {
          show: false,
        },
        track: {
          background: '#f9f9f9',
          strokeWidth: '100%',
          margin: 10,
        },
      },
    },
    colors: ['#5b66eb', '#d7d9fa'],
    stroke: {
      lineCap: 'round'
    },
    labels: ['Students', 'Teachers'],
    legend: {
      show: false,
    }
  };

  var chart = new ApexCharts(document.querySelector("#attendanceChart"), options);
  chart.render();

}

setTimeout(() => {
  renderCharts();
}, 250);