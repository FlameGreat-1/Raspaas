/*
Template Name: Urbix - Admin & Dashboard Template
Author: Pixeleyez
Website: https://pixeleyez.com/
File: echart.init.js
*/


// Basic Line Chart
var basicChartDom = document.getElementById('BasicLineChart');
var basicChart = echarts.init(basicChartDom);
var basicOption = {
  xAxis: {
    type: 'category',
    data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      data: [150, 230, 224, 218, 135, 147, 260],
      type: 'line'
    }
  ],
  grid: {
    top: '5%',
    left: '4%',
    right: '0%',
    bottom: '8%',
  }
};
basicChart.setOption(basicOption);

// Smoothed Line Chart
var smoothedlinechartDom = document.getElementById('SmoothedLineChart');
var smoothedlineChart = echarts.init(smoothedlinechartDom);

var smoothedlineoption = {
  xAxis: {
    type: 'category',
    data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      data: [820, 932, 901, 934, 1290, 1330, 1320],
      type: 'line',
      smooth: true
    }
  ],
  grid: {
    top: '5%',
    left: '4%',
    right: '0%',
    bottom: '8%',
  }
};
smoothedlineChart.setOption(smoothedlineoption);

// Stacked Line Chart
var stackedlinechartDom = document.getElementById('StackedLineChart');
var stackedlineChart = echarts.init(stackedlinechartDom);
var stackedlineOption;

stackedlineOption = {
  title: {
    text: 'Stacked Line'
  },
  tooltip: {
    trigger: 'axis'
  },
  legend: {
    data: ['Email', 'Union Ads', 'Video Ads', 'Direct', 'Search Engine']
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  toolbox: {
    feature: {
      saveAsImage: {}
    }
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      name: 'Email',
      type: 'line',
      stack: 'Total',
      data: [120, 132, 101, 134, 90, 230, 210]
    },
    {
      name: 'Union Ads',
      type: 'line',
      stack: 'Total',
      data: [220, 182, 191, 234, 290, 330, 310]
    },
    {
      name: 'Video Ads',
      type: 'line',
      stack: 'Total',
      data: [150, 232, 201, 154, 190, 330, 410]
    },
    {
      name: 'Direct',
      type: 'line',
      stack: 'Total',
      data: [320, 332, 301, 334, 390, 330, 320]
    },
    {
      name: 'Search Engine',
      type: 'line',
      stack: 'Total',
      data: [820, 932, 901, 934, 1290, 1330, 1320]
    }
  ]
};

stackedlineOption && stackedlineChart.setOption(stackedlineOption);

// Step Line Chart
var stepChartDom = document.getElementById('StepLine');
var stepChart = echarts.init(stepChartDom);
var stepOption = {
  tooltip: {
    trigger: 'axis'
  },
  legend: {
    data: ['Step Start', 'Step Middle', 'Step End']
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true
  },
  toolbox: {
    feature: {
      saveAsImage: {}
    }
  },
  xAxis: {
    type: 'category',
    data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      name: 'Step Start',
      type: 'line',
      step: 'start',
      data: [120, 132, 101, 134, 90, 230, 210]
    },
    {
      name: 'Step Middle',
      type: 'line',
      step: 'middle',
      data: [220, 282, 201, 234, 290, 430, 410]
    },
    {
      name: 'Step End',
      type: 'line',
      step: 'end',
      data: [450, 432, 401, 454, 590, 530, 510]
    }
  ]
};
stepChart.setOption(stepOption);
window.addEventListener('resize', function () {
  stepChart.resize();
});

// Basic Bar Chart

var BasicBarChartDom = document.getElementById('BasicBarChart');
var BasicBarChart = echarts.init(BasicBarChartDom);
var option;

option = {
  xAxis: {
    type: 'category',
    data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      data: [120, 200, 150, 80, 70, 110, 130],
      type: 'bar'
    }
  ],
  grid: {
    top: '10%',
    left: '4%',
    right: '0%',
    bottom: '8%',
  }
};

option && BasicBarChart.setOption(option);

// Simple Example of Dataset Chart

var app = {};

var DatasetChartDom = document.getElementById('DatasetChart');
var DatasetChart = echarts.init(DatasetChartDom);
var option;

option = {
  legend: {},
  tooltip: {},
  dataset: {
    source: [
      ['product', '2015', '2016', '2017'],
      ['Matcha Latte', 43.3, 85.8, 93.7],
      ['Milk Tea', 83.1, 73.4, 55.1],
      ['Cheese Cocoa', 86.4, 65.2, 82.5],
      ['Walnut Brownie', 72.4, 53.9, 39.1]
    ]
  },
  xAxis: { type: 'category' },
  yAxis: {},
  // Declare several bar series, each will be mapped
  // to a column of dataset.source by default.
  series: [{ type: 'bar' }, { type: 'bar' }, { type: 'bar' }],
  grid: {
    top: '10%',
    left: '4%',
    right: '0%',
    bottom: '8%',
  }
};

option && DatasetChart.setOption(option);

// Basic Scatter Chart
var basicscatterchartDom = document.getElementById('BasicScatterChart');
var basicscatterChart = echarts.init(basicscatterchartDom);
var basicscatterOption;

basicscatterOption = {
  xAxis: {},
  yAxis: {},
  series: [
    {
      symbolSize: 20,
      data: [
        [10.0, 8.04],
        [8.07, 6.95],
        [13.0, 7.58],
        [9.05, 8.81],
        [11.0, 8.33],
        [14.0, 7.66],
        [13.4, 6.81],
        [10.0, 6.33],
        [14.0, 8.96],
        [12.5, 6.82],
        [9.15, 7.2],
        [11.5, 7.2],
        [3.03, 4.23],
        [12.2, 7.83],
        [2.02, 4.47],
        [1.05, 3.33],
        [4.05, 4.96],
        [6.03, 7.24],
        [12.0, 6.26],
        [12.0, 8.84],
        [7.08, 5.82],
        [5.02, 5.68]
      ],
      type: 'scatter'
    }
  ],
  grid: {
    top: '5%',
    left: '4%',
    right: '0%',
    bottom: '8%',
  }
};
basicscatterOption && basicscatterChart.setOption(basicscatterOption);

// Basic Radar Chart
var BasicRadarChartDom = document.getElementById('BasicRadarChart');
var BasicRadarChart = echarts.init(BasicRadarChartDom);
var BasicRadarOption = {
  legend: {
    data: ['Allocated Budget', 'Actual Spending']
  },
  radar: {
    indicator: [
      { name: 'Sales', max: 6500 },
      { name: 'Administration', max: 16000 },
      { name: 'Information Technology', max: 30000 },
      { name: 'Customer Support', max: 38000 },
      { name: 'Development', max: 52000 },
      { name: 'Marketing', max: 25000 }
    ]
  },
  series: [
    {
      name: 'Budget vs spending',
      type: 'radar',
      data: [
        {
          value: [4200, 3000, 20000, 35000, 50000, 18000],
          name: 'Allocated Budget'
        },
        {
          value: [5000, 14000, 28000, 26000, 42000, 21000],
          name: 'Actual Spending'
        }
      ]
    }
  ],
  grid: {
    top: '5%',
    left: '4%',
    right: '0%',
    bottom: '8%',
  }
};
BasicRadarChart.setOption(BasicRadarOption);


// Nightingale Chart
var NightingaleChartDom = document.getElementById('NightingaleChart');
var NightingaleChart = echarts.init(NightingaleChartDom);
var option;

option = {
  legend: {
    top: 'bottom'
  },
  toolbox: {
    show: true,
    feature: {
      mark: { show: true },
      dataView: { show: true, readOnly: false },
      restore: { show: true },
      saveAsImage: { show: true }
    }
  },
  series: [
    {
      name: 'Nightingale Chart',
      type: 'pie',
      radius: [50, 130],
      center: ['50%', '50%'],
      roseType: 'area',
      itemStyle: {
        borderRadius: 8
      },
      data: [
        { value: 40, name: 'rose 1' },
        { value: 38, name: 'rose 2' },
        { value: 32, name: 'rose 3' },
        { value: 30, name: 'rose 4' },
        { value: 28, name: 'rose 5' },
        { value: 26, name: 'rose 6' },
        { value: 22, name: 'rose 7' },
        { value: 18, name: 'rose 8' }
      ]
    }
  ]
};

option && NightingaleChart.setOption(option);

// Basic Candlestick Chart

// Ensure the DOM element exists
var BasicCandlestickChartDom = document.getElementById('BasicCandlestickChart');
if (!BasicCandlestickChartDom) {
    console.error("Chart container not found!");
} else {
    var BasicCandlestickChart = echarts.init(BasicCandlestickChartDom);

    var option = {
        title: {
            text: 'Basic Candlestick Chart',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            }
        },
        grid: {
            top: '10%',
            left: '4%',
            right: '0%',
            bottom: '8%',
          },
        xAxis: {
            type: 'category',
            data: ['2017-10-24', '2017-10-25', '2017-10-26', '2017-10-27'],
            axisLine: { lineStyle: { color: '#777' } }
        },
        yAxis: {
            type: 'value',
            scale: true,
            axisLine: { lineStyle: { color: '#777' } },
            splitLine: { show: true, lineStyle: { type: 'dashed' } }
        },
        series: [
            {
                name: 'Candlestick',
                type: 'candlestick',
                data: [
                    [20, 34, 10, 38], // Open, Close, Lowest, Highest
                    [40, 35, 30, 50],
                    [31, 38, 33, 44],
                    [38, 15, 5, 42]
                ],
                itemStyle: {
                    color: '#00da3c',  // Bullish (Up)
                    color0: '#ec0000', // Bearish (Down)
                    borderColor: '#00da3c',
                    borderColor0: '#ec0000'
                }
            }
        ]
    };

    // Apply the chart options
    BasicCandlestickChart.setOption(option);

    // Handle chart resizing
    window.addEventListener('resize', function () {
        BasicCandlestickChart.resize();
    });
}

// Graph on Cartesian Chart

var GraphonCartesianChartDom = document.getElementById('GraphonCartesianChart');
var GraphonCartesianChart = echarts.init(GraphonCartesianChartDom);
var option;

const axisData = ['Mon', 'Tue', 'Wed', 'Very Loooong Thu', 'Fri', 'Sat', 'Sun'];
const data = axisData.map(function (item, i) {
  return Math.round(Math.random() * 1000 * (i + 1));
});
const links = data.map(function (item, i) {
  return {
    source: i,
    target: i + 1
  };
});
links.pop();
option = {
  tooltip: {},
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: axisData
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      type: 'graph',
      layout: 'none',
      coordinateSystem: 'cartesian2d',
      symbolSize: 40,
      label: {
        show: true
      },
      edgeSymbol: ['circle', 'arrow'],
      edgeSymbolSize: [4, 10],
      data: data,
      links: links,
      lineStyle: {
        color: '#2f4554'
      }
    }
  ],
  grid: {
    top: '10%',
    left: '4%',
    right: '3%',
    bottom: '8%',
  }
};

option && GraphonCartesianChart.setOption(option);

// Simple Gauge Chart

var SimpleGaugeChartDom = document.getElementById('SimpleGaugeChart');
var SimpleGaugeChart = echarts.init(SimpleGaugeChartDom);
var option;

option = {
  tooltip: {
    formatter: '{a} <br/>{b} : {c}%'
  },
  series: [
    {
      name: 'Pressure',
      type: 'gauge',
      progress: {
        show: true
      },
      detail: {
        valueAnimation: true,
        formatter: '{value}'
      },
      data: [
        {
          value: 50,
          name: 'SCORE'
        }
      ]
    }
  ]
};

option && SimpleGaugeChart.setOption(option);

// Basic Sankey Chart

var BasicSankeyChartDom = document.getElementById('BasicSankeyChart');
var BasicSankeyChart = echarts.init(BasicSankeyChartDom);
var option;

option = {
  series: {
    type: 'sankey',
    layout: 'none',
    emphasis: {
      focus: 'adjacency'
    },
    data: [
      {
        name: 'a'
      },
      {
        name: 'b'
      },
      {
        name: 'a1'
      },
      {
        name: 'a2'
      },
      {
        name: 'b1'
      },
      {
        name: 'c'
      }
    ],
    links: [
      {
        source: 'a',
        target: 'a1',
        value: 5
      },
      {
        source: 'a',
        target: 'a2',
        value: 3
      },
      {
        source: 'b',
        target: 'b1',
        value: 8
      },
      {
        source: 'a',
        target: 'b1',
        value: 3
      },
      {
        source: 'b1',
        target: 'a1',
        value: 1
      },
      {
        source: 'b1',
        target: 'c',
        value: 2
      }
    ]
  }
};

option && BasicSankeyChart.setOption(option);

// Customized Funnel Chart

var CustomizedFunnelChartDom = document.getElementById('CustomizedFunnelChart');
var CustomizedFunnelChart = echarts.init(CustomizedFunnelChartDom);
var option;

option = {
  tooltip: {
    trigger: 'item',
    formatter: '{a} <br/>{b} : {c}%'
  },
  toolbox: {
    feature: {
      dataView: { readOnly: false },
      restore: {},
      saveAsImage: {}
    }
  },
  legend: {
    data: ['Show', 'Click', 'Visit', 'Inquiry', 'Order']
  },
  series: [
    {
      name: 'Expected',
      type: 'funnel',
      left: '10%',
      width: '80%',
      label: {
        formatter: '{b}Expected'
      },
      labelLine: {
        show: false
      },
      itemStyle: {
        opacity: 0.7
      },
      emphasis: {
        label: {
          position: 'inside',
          formatter: '{b}Expected: {c}%'
        }
      },
      data: [
        { value: 60, name: 'Visit' },
        { value: 40, name: 'Inquiry' },
        { value: 20, name: 'Order' },
        { value: 80, name: 'Click' },
        { value: 100, name: 'Show' }
      ]
    },
    {
      name: 'Actual',
      type: 'funnel',
      left: '10%',
      width: '80%',
      maxSize: '80%',
      label: {
        position: 'inside',
        formatter: '{c}%',
        color: '#fff'
      },
      itemStyle: {
        opacity: 0.5,
        borderColor: '#fff',
        borderWidth: 2
      },
      emphasis: {
        label: {
          position: 'inside',
          formatter: '{b}Actual: {c}%'
        }
      },
      data: [
        { value: 30, name: 'Visit' },
        { value: 10, name: 'Inquiry' },
        { value: 5, name: 'Order' },
        { value: 50, name: 'Click' },
        { value: 80, name: 'Show' }
      ],
      // Ensure outer shape will not be over inner shape when hover.
      z: 100
    }
  ],
};

option && CustomizedFunnelChart.setOption(option);




