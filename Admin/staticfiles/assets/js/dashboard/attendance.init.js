document.addEventListener('DOMContentLoaded', function() {
        if (typeof ApexCharts === 'undefined') {
            console.error('ApexCharts library is not loaded!');
            return;
        }
        console.log('ApexCharts library is loaded successfully');
        
    setTimeout(function() {
        const monthlyChartEl = document.querySelector("#monthlyAttendanceChart");
        const rateChartEl = document.querySelector("#attendanceRateChart");
        const dailyChartEl = document.querySelector("#dailyAttendanceChart");
        
        try {
            let presentData = [45, 52, 38, 24, 33, 26, 21, 20, 6, 8, 15, 10];
            let absentData = [35, 41, 62, 42, 13, 18, 29, 37, 36, 51, 32, 35];
            let leaveData = [87, 57, 74, 99, 75, 38, 62, 47, 82, 56, 45, 47];
            let categories = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
            
            if (monthlyChartEl && monthlyChartEl.getAttribute('data-present')) {
                try {
                    presentData = JSON.parse(monthlyChartEl.getAttribute('data-present').replace(/'/g, '"'));
                } catch (e) {
                    console.error("Error parsing present data:", e);
                }
            }
            
            if (monthlyChartEl && monthlyChartEl.getAttribute('data-absent')) {
                try {
                    absentData = JSON.parse(monthlyChartEl.getAttribute('data-absent').replace(/'/g, '"'));
                } catch (e) {
                    console.error("Error parsing absent data:", e);
                }
            }
            
            if (monthlyChartEl && monthlyChartEl.getAttribute('data-leave')) {
                try {
                    leaveData = JSON.parse(monthlyChartEl.getAttribute('data-leave').replace(/'/g, '"'));
                } catch (e) {
                    console.error("Error parsing leave data:", e);
                }
            }
            
            if (monthlyChartEl && monthlyChartEl.getAttribute('data-categories')) {
                try {
                    categories = JSON.parse(monthlyChartEl.getAttribute('data-categories').replace(/'/g, '"'));
                } catch (e) {
                    console.error("Error parsing categories:", e);
                }
            }
            
            if (monthlyChartEl) {
                var monthlyAttendanceOptions = {
                    series: [{
                        name: 'Present',
                        data: presentData
                    }, {
                        name: 'Absent',
                        data: absentData
                    }, {
                        name: 'On Leave',
                        data: leaveData
                    }],
                    chart: {
                        type: 'bar',
                        height: 350,
                        stacked: true,
                        toolbar: {
                            show: false
                        }
                    },
                    plotOptions: {
                        bar: {
                            horizontal: false,
                            columnWidth: '55%',
                            endingShape: 'rounded'
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
                    xaxis: {
                        categories: categories,
                    },
                    yaxis: {
                        title: {
                            text: 'Employees'
                        }
                    },
                    fill: {
                        opacity: 1
                    },
                    tooltip: {
                        y: {
                            formatter: function (val) {
                                return val + " employees"
                            }
                        }
                    },
                    colors: ['#0ab39c', '#f06548', '#405189']
                };
                
                var monthlyAttendanceChart = new ApexCharts(monthlyChartEl, monthlyAttendanceOptions);
                monthlyAttendanceChart.render();
            }
            
            let percentage = 84;
            if (rateChartEl && rateChartEl.getAttribute('data-percentage')) {
                percentage = parseFloat(rateChartEl.getAttribute('data-percentage'));
            }
            
            if (rateChartEl) {
                var attendanceRateOptions = {
                    series: [percentage],
                    chart: {
                        height: 250,
                        type: 'radialBar',
                    },
                    plotOptions: {
                        radialBar: {
                            hollow: {
                                size: '70%',
                            },
                            dataLabels: {
                                name: {
                                    show: false,
                                },
                                value: {
                                    fontSize: '30px',
                                    show: true,
                                    formatter: function (val) {
                                        return val + '%'
                                    }
                                }
                            }
                        }
                    },
                    fill: {
                        colors: ['#405189']
                    },
                    labels: ['Attendance'],
                };
                
                var attendanceRateChart = new ApexCharts(rateChartEl, attendanceRateOptions);
                attendanceRateChart.render();
            }
            
            let attendanceData = [78, 82, 85, 90, 87, 92, 80, 85, 89, 92, 94, 90];
            let dailyCategories = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
            
            if (dailyChartEl && dailyChartEl.getAttribute('data-percentages')) {
                try {
                    attendanceData = JSON.parse(dailyChartEl.getAttribute('data-percentages').replace(/'/g, '"'));
                } catch (e) {
                    console.error("Error parsing percentages data:", e);
                }
            }
            
            if (dailyChartEl && dailyChartEl.getAttribute('data-categories')) {
                try {
                    dailyCategories = JSON.parse(dailyChartEl.getAttribute('data-categories').replace(/'/g, '"'));
                } catch (e) {
                    console.error("Error parsing daily categories:", e);
                }
            }
            
            if (dailyChartEl) {
                var dailyAttendanceOptions = {
                    series: [{
                        name: 'Attendance',
                        data: attendanceData
                    }],
                    chart: {
                        height: 250,
                        type: 'line',
                        zoom: {
                            enabled: false
                        },
                        toolbar: {
                            show: false
                        }
                    },
                    dataLabels: {
                        enabled: false
                    },
                    stroke: {
                        curve: 'smooth',
                        width: 3
                    },
                    grid: {
                        row: {
                            colors: ['#f3f3f3', 'transparent'],
                            opacity: 0.5
                        },
                    },
                    xaxis: {
                        categories: dailyCategories,
                    },
                    yaxis: {
                        min: 0,
                        max: 100,
                        labels: {
                            formatter: function (val) {
                                return val.toFixed(0) + '%';
                            }
                        }
                    },
                    colors: ['#0ab39c']
                };
                
                var dailyAttendanceChart = new ApexCharts(dailyChartEl, dailyAttendanceOptions);
                dailyAttendanceChart.render();
            }
            
            const startDateInput = document.getElementById('start_date');
            const endDateInput = document.getElementById('end_date');
            
            if (endDateInput && startDateInput) {
                endDateInput.addEventListener('change', function() {
                    if (startDateInput.value && this.value) {
                        if (new Date(this.value) < new Date(startDateInput.value)) {
                            alert('End date cannot be earlier than start date');
                            this.value = startDateInput.value;
                        }
                    }
                });
                
                startDateInput.addEventListener('change', function() {
                    if (endDateInput.value && this.value) {
                        if (new Date(this.value) > new Date(endDateInput.value)) {
                            endDateInput.value = this.value;
                        }
                    }
                });
            }
        } catch (error) {
            console.error("Error rendering charts:", error);
        }
    }, 250);
});
