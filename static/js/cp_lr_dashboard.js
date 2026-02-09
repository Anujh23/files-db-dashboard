// static/js/cp_lr_dashboard.js
let currentChart = null;
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
const monthNames = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

function formatNumberIndian(num) {
    if (!num) return '0';
    let numStr = num.toString();
    let lastThree = numStr.substring(numStr.length - 3);
    let otherNumbers = numStr.substring(0, numStr.length - 3);
    if (otherNumbers !== '') {
        lastThree = ',' + lastThree;
    }
    return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;
}

function formatAchievement(value) {
    if (!value) return '₹0';
    if (value >= 10000000) return '₹' + (value / 10000000).toFixed(2) + ' Cr';
    if (value >= 100000) return '₹' + (value / 100000).toFixed(2) + ' L';
    if (value >= 1000) return '₹' + (value / 1000).toFixed(0) + 'K';
    return '₹' + formatNumberIndian(value);
}

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

function updateMonthDisplay() {
    document.getElementById('current-month').textContent = `${monthNames[currentMonth]} ${currentYear}`;
}

function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    } else if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    }
    updateMonthDisplay();
    updateAllData();
}

async function updateTop3(source, listId, timeId) {
    const url = source === 'CP'
        ? `/api/cp-top3?month=${currentMonth + 1}&year=${currentYear}`
        : `/api/lr-top3?month=${currentMonth + 1}&year=${currentYear}`;

    const list = document.getElementById(listId);
    list.innerHTML = '';

    try {
        const res = await fetch(url);
        const data = await res.json();

        const items = (data.top3 || []).slice(0, 3);
        if (!items.length) {
            list.innerHTML = '<li class="top-item">No data</li>';
        } else {
            items.forEach((item, idx) => {
                const li = document.createElement('li');
                li.className = 'top-item';
                li.innerHTML = `
                    <span class="rank-number">${idx + 1}</span>
                    <span class="achiever-name">${item.CM_Name}</span>
                    <span class="achievement-value">${formatAchievement(item.Achievement)}</span>
                `;
                list.appendChild(li);
            });
        }

        updateTimeDisplay(timeId);
    } catch (e) {
        list.innerHTML = '<li class="top-item">Error loading data</li>';
    }
}

async function updateTopState(source) {
    const url = source === 'CP'
        ? `/api/cp-top-state?month=${currentMonth + 1}&year=${currentYear}`
        : `/api/lr-top-state?month=${currentMonth + 1}&year=${currentYear}`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        if (source === 'CP') {
            document.getElementById('cp-top-state-name').textContent = data.state || '—';
            document.getElementById('cp-top-state-value').textContent = formatAchievement(data.total);
        } else {
            document.getElementById('lr-top-state-name').textContent = data.state || '—';
            document.getElementById('lr-top-state-value').textContent = formatAchievement(data.total);
        }
    } catch (e) {
        // ignore
    }
}

async function updateStats() {
    try {
        const res = await fetch(`/api/cp-lr-stats?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        document.getElementById('cp-score').textContent = `${data.cp_score || 0}%`;
        document.getElementById('lr-score').textContent = `${data.lr_score || 0}%`;

        document.getElementById('cp-progress-bar').style.width = `${data.cp_progress_pct || 0}%`;
        document.getElementById('lr-progress-bar').style.width = `${data.lr_progress_pct || 0}%`;

        document.getElementById('cp-progress-text').textContent = `${data.cp_progress_pct || 0}% of ${formatAchievement(data.cp_target)} (${formatAchievement(data.cp_total)})`;
        document.getElementById('lr-progress-text').textContent = `${data.lr_progress_pct || 0}% of ${formatAchievement(data.lr_target)} (${formatAchievement(data.lr_total)})`;

        document.getElementById('focus-bar').style.width = `${data.combined_progress_pct || 0}%`;
        document.getElementById('focus-text').textContent = `${data.combined_progress_pct || 0}% of ${formatAchievement(data.combined_target)} (${formatAchievement(data.combined_total)})`;
    } catch (e) {
    }
}

async function updateGraph() {
    try {
        const res = await fetch(`/api/cp-lr-daily?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        const cpRaw = data.cp_daily_totals || [];
        const lrRaw = data.lr_daily_totals || [];
        const days = data.days || cpRaw.map((_, i) => i + 1);

        const divisor = 100000;
        const cp = cpRaw.map(v => v / divisor);
        const lr = lrRaw.map(v => v / divisor);

        const maxValue = Math.max(...cp, ...lr) * 1.1;

        if (currentChart) currentChart.destroy();

        const ctx = document.getElementById('dailyGraph').getContext('2d');
        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: days,
                datasets: [
                    {
                        label: 'CP',
                        data: cp,
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
                        label: 'LR',
                        data: lr,
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
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const raw = (ctx.raw || 0) * divisor;
                                return `${ctx.dataset.label}: ${formatAchievement(raw)}`;
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
                            callback: (v) => v >= 100 ? `${(v / 100).toFixed(2)} Cr` : `${v} L`
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
    } catch (e) {
        // ignore
    }
}

async function updateAllData() {
    await Promise.all([
        updateTop3('CP', 'cp-list', 'cp-time'),
        updateTop3('LR', 'lr-list', 'lr-time'),
        updateTopState('CP'),
        updateTopState('LR'),
        updateStats(),
        updateGraph(),
    ]);
}

document.addEventListener('DOMContentLoaded', () => {
    updateMonthDisplay();
    updateAllData();
    setInterval(updateAllData, 30000);
});
