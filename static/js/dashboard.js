// static/js/dashboard.js
// Global variables
let currentChart = null;
let currentMonth = new Date().getMonth(); // Current month (0-indexed)
let currentYear = new Date().getFullYear(); // Current year
let timePeriod = 'month';
const monthNames = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

// Indian number formatting with commas
function formatNumberIndian(num) {
    if (!num) return '0';

    // Indian numbering system: 1,00,00,000 format
    let numStr = num.toString();
    let lastThree = numStr.substring(numStr.length - 3);
    let otherNumbers = numStr.substring(0, numStr.length - 3);

    if (otherNumbers !== '') {
        lastThree = ',' + lastThree;
    }

    let result = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;

    return result;
}

// Format numbers with commas
function formatNumber(num) {
    return formatNumberIndian(num);
}

// Format achievement value for Indian market (Cr and Lakhs)
function formatAchievement(value) {
    if (!value) return '₹0';

    // Convert to Indian numbering system
    if (value >= 10000000) { // 1 Crore = 10,000,000
        return '₹' + (value / 10000000).toFixed(2) + ' Cr';
    } else if (value >= 100000) { // 1 Lakh = 100,000
        return '₹' + (value / 100000).toFixed(2) + ' L';
    } else if (value >= 1000) {
        return '₹' + (value / 1000).toFixed(0) + 'K';
    }
    return '₹' + formatNumber(value);
}

// Determine the best unit based on data values
function determineBestUnit(values) {
    // Find the maximum value in the dataset
    const maxValue = Math.max(...values);

    // If data is mostly in Crores (> 50 Lakhs on average)
    if (maxValue >= 5000000) { // 50 Lakhs or more
        return {
            unit: 'Cr',
            divisor: 10000000,
            label: '₹ Cr',
            tooltipDivisor: 10000000,
            precision: 2
        };
    }
    // If data is mostly in Lakhs (1 Lakh to 50 Lakhs)
    else if (maxValue >= 100000) { // 1 Lakh or more
        return {
            unit: 'L',
            divisor: 100000,
            label: '₹ Lakhs',
            tooltipDivisor: 100000,
            precision: 2
        };
    }
    // Smaller values (in thousands)
    else {
        return {
            unit: 'K',
            divisor: 1000,
            label: '₹ Thousands',
            tooltipDivisor: 1000,
            precision: 1
        };
    }
}

// Format tooltip value appropriately
function formatTooltipValue(value, unitInfo = null) {
    if (value >= 10000000) {
        return '₹' + (value / 10000000).toFixed(2) + ' Cr';
    } else if (value >= 100000) {
        return '₹' + (value / 100000).toFixed(2) + ' L';
    } else if (value >= 1000) {
        return '₹' + (value / 1000).toFixed(0) + 'K';
    }
    return '₹' + formatNumber(value);
}

// Update time display
function updateTimeDisplay(elementId) {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById(elementId).textContent = `Updated: ${timeString}`;
}

// Update month display - ALWAYS SHOW CURRENT MONTH
function updateMonthDisplay() {
    const now = new Date();
    currentMonth = now.getMonth();
    currentYear = now.getFullYear();
    document.getElementById('current-month').textContent =
        `${monthNames[currentMonth]} ${currentYear}`;
}

// Set time period
function setTimePeriod(period) {
    timePeriod = period;
    document.querySelectorAll('.time-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
    updateGraph();
}

// Fetch and update ELI data
async function updateELIData() {
    try {
        const response = await fetch(`/api/eli-top3?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await response.json();

        const eliList = document.getElementById('eli-list');
        eliList.innerHTML = '';

        // Update top 3 list
        data.top3.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = 'top-item';
            li.innerHTML = `
                <span class="rank-number">${index + 1}</span>
                <span class="achiever-name">${item.CM_Name}</span>
                <span class="achievement-value">${formatAchievement(item.Achievement)}</span>
            `;
            eliList.appendChild(li);
        });

        // Update time
        updateTimeDisplay('eli-time');

    } catch (error) {
        console.error('Error fetching ELI data:', error);
        document.getElementById('eli-list').innerHTML =
            '<li class="top-item">Error loading data</li>';
    }
}

// Fetch and update ELI top state
async function updateELITopState() {
    try {
        const res = await fetch(`/api/eli-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        document.getElementById('eli-top-state-name').textContent =
            data.state || '—';

        document.getElementById('eli-top-state-value').textContent =
            formatAchievement(data.total);

    } catch (err) {
        console.error('ELI Top State error', err);
        document.getElementById('eli-top-state-name').textContent = '—';
        document.getElementById('eli-top-state-value').textContent = '₹0';
    }
}

// Fetch and update NBL data
async function updateNBLData() {
    try {
        const response = await fetch(`/api/nbl-top3?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await response.json();

        const nblList = document.getElementById('nbl-list');
        nblList.innerHTML = '';

        // Update top 3 list
        data.top3.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = 'top-item';
            li.innerHTML = `
                <span class="rank-number">${index + 1}</span>
                <span class="achiever-name">${item.CM_Name}</span>
                <span class="achievement-value">${formatAchievement(item.Achievement)}</span>
            `;
            nblList.appendChild(li);
        });

        // Update time
        updateTimeDisplay('nbl-time');

    } catch (error) {
        console.error('Error fetching NBL data:', error);
        document.getElementById('nbl-list').innerHTML =
            '<li class="top-item">Error loading data</li>';
    }
}

// Fetch and update NBL top state
async function updateNBLTopState() {
    try {
        const res = await fetch(`/api/nbl-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        document.getElementById('nbl-top-state-name').textContent =
            data.state || '—';

        document.getElementById('nbl-top-state-value').textContent =
            formatAchievement(data.total);

    } catch (err) {
        console.error('NBL Top State error', err);
        document.getElementById('nbl-top-state-name').textContent = '—';
        document.getElementById('nbl-top-state-value').textContent = '₹0';
    }
}

// Fetch and update dashboard stats
async function updateDashboardStats() {
    try {
        const response = await fetch(`/api/dashboard-stats?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await response.json();

        // Update ELI score
        document.getElementById('eli-score').textContent = `${data.eli_score}%`;
        const eliTrend = document.getElementById('eli-trend');
        eliTrend.className = 'metric-trend trend-up';
        eliTrend.innerHTML = `<span>↑</span><span>Live</span>`;
        document.getElementById('eli-update').textContent = `Live`;

        // ELI progress bar
        document.getElementById('eli-progress-bar').style.width = `${data.eli_progress_pct}%`;
        document.getElementById('eli-progress-text').textContent =
            `${data.eli_progress_pct}% of ₹4.25 Cr (${formatAchievement(data.eli_total)})`;

        // Update NBL score
        document.getElementById('nbl-score').textContent = `${data.nbl_score}%`;
        const nblTrend = document.getElementById('nbl-trend');
        nblTrend.className = 'metric-trend trend-up';
        nblTrend.innerHTML = `<span>↑</span><span>Live</span>`;
        document.getElementById('nbl-update').textContent = `Live`;

        // NBL progress bar
        document.getElementById('nbl-progress-bar').style.width = `${data.nbl_progress_pct}%`;
        document.getElementById('nbl-progress-text').textContent =
            `${data.nbl_progress_pct}% of ₹5 Cr (${formatAchievement(data.nbl_total)})`;

        // Company total progress
        document.getElementById('focus-bar').style.width = `${data.leader_progress_pct}%`;
        document.getElementById('focus-text').textContent =
            `${data.leader_progress_pct}% of ₹9.25 Cr (${formatAchievement(data.combined_total)})`;

        // Update welcome text
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-IN', {
            hour12: true,
            hour: '2-digit',
            minute: '2-digit'
        });
        document.querySelector('.welcome-text').textContent =
            `Current Month Dashboard • ${timeString}`;

    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
    }
}

// Update graph with daily data
async function updateGraph() {
    try {
        const response = await fetch(`/api/daily-performance?month=${currentMonth + 1}&year=${currentYear}&period=${timePeriod}`);
        const data = await response.json();

        // Prepare raw data
        const eliRawData = data.eli_daily_totals;
        const nblRawData = data.nbl_daily_totals;

        // Plot values in Lakhs (L). For y-axis labels, switch to Cr when large.
        const graphDivisor = 100000; // 1 Lakh
        const eliData = eliRawData.map(total => total / graphDivisor);
        const nblData = nblRawData.map(total => total / graphDivisor);

        // Update graph title
        // document.getElementById('graph-title').textContent = `Daily Performance: ${data.current_month}`;

        // Clean up any existing custom elements
        const existingXAxis = document.querySelector('.custom-x-axis');
        if (existingXAxis) {
            existingXAxis.remove();
        }

        // Destroy existing chart
        if (currentChart) {
            currentChart.destroy();
        }

        // Create new chart
        const ctx = document.getElementById('dailyGraph').getContext('2d');
        const maxValue = Math.max(...eliData, ...nblData) * 1.1;

        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.days || eliData.map((_, i) => `Day ${i + 1}`), // Show days from data or fallback to Day 1, Day 2, etc.
                datasets: [
                    {
                        label: 'ELI',
                        data: eliData,
                        borderColor: '#5d9cec',
                        backgroundColor: 'rgba(93, 156, 236, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#5d9cec',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    },
                    {
                        label: 'NBL',
                        data: nblData,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#8b5cf6',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const dataset = context.dataset.label;
                                const chartValue = context.raw;
                                const rawValue = chartValue * graphDivisor;
                                const formatted = formatTooltipValue(rawValue);
                                return `${dataset}: ${formatted}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(179, 189, 202, 0.2)'
                        },
                        ticks: {
                            color: '#6c7a89',
                            callback: function (value) {
                                // value is in Lakhs since we plot in Lakhs
                                if (value >= 100) {
                                    const cr = value / 100;
                                    return `${cr.toFixed(2)} Cr`;
                                }
                                return `${value} L`;
                            }
                        },
                        title: {
                            display: false
                        },
                        suggestedMax: maxValue
                    },
                    x: {
                        display: true,
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#6c7a89',
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 15
                        }
                    }
                },
                layout: {
                    padding: {
                        bottom: 10 // Reduced padding since we're not using custom labels
                    }
                }
            }
        });


    } catch (error) {
        console.error('Error fetching graph data:', error);
    }
}

// Update all data
async function updateAllData() {
    await Promise.all([
        updateELIData(),
        updateNBLData(),
        updateDashboardStats(),
        updateGraph(),
        updateELITopState(),
        updateNBLTopState()
    ]);
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
    updateMonthDisplay();
    updateAllData();

    // Auto-refresh every 30 seconds
    setInterval(updateAllData, 30000);
});