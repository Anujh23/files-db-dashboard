// static/js/cp_lr_dashboard.js
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

// Update month display
function updateMonthDisplay() {
    const now = new Date();
    currentMonth = now.getMonth();
    currentYear = now.getFullYear();
    document.getElementById('current-month').textContent =
        `${monthNames[currentMonth]} ${currentYear}`;
}

// Change month
function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    } else if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    }
    document.getElementById('current-month').textContent =
        `${monthNames[currentMonth]} ${currentYear}`;
    updateAllData();
}

// Fetch and update CP data
async function updateCPData() {
    try {
        const response = await fetch(`/api/cp-top3?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await response.json();

        const cpList = document.getElementById('cp-list');
        cpList.innerHTML = '';

        // Update top 3 list
        data.top3.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = 'top-item';
            li.innerHTML = `
                <span class="rank-number">${index + 1}</span>
                <span class="achiever-name">${item.CM_Name}</span>
                <span class="achievement-value">${formatAchievement(item.Achievement)}</span>
            `;
            cpList.appendChild(li);
        });

        // Update time
        updateTimeDisplay('cp-time');

    } catch (error) {
        console.error('Error fetching CP data:', error);
        document.getElementById('cp-list').innerHTML =
            '<li class="top-item">Error loading data</li>';
    }
}

// Fetch and update CP top state
async function updateCPTopState() {
    try {
        const res = await fetch(`/api/cp-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        document.getElementById('cp-top-state-name').textContent =
            data.state || '—';

        document.getElementById('cp-top-state-value').textContent =
            formatAchievement(data.total);

    } catch (err) {
        console.error('CP Top State error', err);
        document.getElementById('cp-top-state-name').textContent = '—';
        document.getElementById('cp-top-state-value').textContent = '₹0';
    }
}

// Fetch and update LR data
async function updateLRData() {
    try {
        const response = await fetch(`/api/lr-top3?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await response.json();

        const lrList = document.getElementById('lr-list');
        lrList.innerHTML = '';

        // Update top 3 list
        data.top3.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = 'top-item';
            li.innerHTML = `
                <span class="rank-number">${index + 1}</span>
                <span class="achiever-name">${item.CM_Name}</span>
                <span class="achievement-value">${formatAchievement(item.Achievement)}</span>
            `;
            lrList.appendChild(li);
        });

        // Update time
        updateTimeDisplay('lr-time');

    } catch (error) {
        console.error('Error fetching LR data:', error);
        document.getElementById('lr-list').innerHTML =
            '<li class="top-item">Error loading data</li>';
    }
}

// Fetch and update LR top state
async function updateLRTopState() {
    try {
        const res = await fetch(`/api/lr-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        document.getElementById('lr-top-state-name').textContent =
            data.state || '—';

        document.getElementById('lr-top-state-value').textContent =
            formatAchievement(data.total);

    } catch (err) {
        console.error('LR Top State error', err);
        document.getElementById('lr-top-state-name').textContent = '—';
        document.getElementById('lr-top-state-value').textContent = '₹0';
    }
}

// Fetch and update dashboard stats
async function updateDashboardStats() {
    try {
        const response = await fetch(`/api/cp-lr-stats?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await response.json();

        // Update CP score
        document.getElementById('cp-score').textContent = `${data.cp_score}%`;
        const cpTrend = document.getElementById('cp-trend');
        cpTrend.className = 'metric-trend trend-up';
        cpTrend.innerHTML = `<span>↑</span><span>Live</span>`;
        document.getElementById('cp-update').textContent = `Live`;

        // CP progress bar
        document.getElementById('cp-progress-bar').style.width = `${data.cp_progress_pct}%`;
        document.getElementById('cp-progress-text').textContent =
            `${data.cp_progress_pct}% of ₹5 Cr (${formatAchievement(data.cp_total)})`;

        // Update LR score
        document.getElementById('lr-score').textContent = `${data.lr_score}%`;
        const lrTrend = document.getElementById('lr-trend');
        lrTrend.className = 'metric-trend trend-up';
        lrTrend.innerHTML = `<span>↑</span><span>Live</span>`;
        document.getElementById('lr-update').textContent = `Live`;

        // LR progress bar
        document.getElementById('lr-progress-bar').style.width = `${data.lr_progress_pct}%`;
        document.getElementById('lr-progress-text').textContent =
            `${data.lr_progress_pct}% of ₹5 Cr (${formatAchievement(data.lr_total)})`;

        // Combined progress
        document.getElementById('focus-bar').style.width = `${data.combined_progress_pct}%`;
        document.getElementById('focus-text').textContent =
            `${data.combined_progress_pct}% of ₹10 Cr (${formatAchievement(data.combined_total)})`;

    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
    }
}

// Update graph with daily data
async function updateGraph() {
    try {
        const response = await fetch(`/api/cp-lr-daily?month=${currentMonth + 1}&year=${currentYear}&period=${timePeriod}`);
        const data = await response.json();

        // Prepare raw data
        const cpRawData = data.cp_daily_totals;
        const lrRawData = data.lr_daily_totals;

        // Plot values in Lakhs (L)
        const graphDivisor = 100000; // 1 Lakh
        const cpData = cpRawData.map(total => total / graphDivisor);
        const lrData = lrRawData.map(total => total / graphDivisor);

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
        const maxValue = Math.max(...cpData, ...lrData) * 1.1;

        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.days || cpData.map((_, i) => `Day ${i + 1}`),
                datasets: [
                    {
                        label: 'CP',
                        data: cpData,
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#ff6b6b',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    },
                    {
                        label: 'LR',
                        data: lrData,
                        borderColor: '#4ecdc4',
                        backgroundColor: 'rgba(78, 205, 196, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#4ecdc4',
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
                        bottom: 10
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
        updateCPData(),
        updateLRData(),
        updateDashboardStats(),
        updateGraph(),
        updateCPTopState(),
        updateLRTopState()
    ]);
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
    updateMonthDisplay();
    updateAllData();

    // Auto-refresh every 30 seconds
    setInterval(updateAllData, 30000);
});
