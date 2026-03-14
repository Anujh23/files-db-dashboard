// static/js/cp_lr_dashboard.js
let currentChart = null;
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();

async function updateTop3(source, listId, timeId) {
    const list = document.getElementById(listId);
    list.innerHTML = '';
    try {
        const src = source.toLowerCase();
        const res = await fetch(`/api/${src}-top3?month=${currentMonth + 1}&year=${currentYear}`);
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
        console.error(`Error fetching ${source} top3:`, e);
        list.innerHTML = '<li class="top-item">Error loading data</li>';
    }
}

async function updateTopState(source) {
    const src = source.toLowerCase();
    try {
        const res = await fetch(`/api/${src}-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        document.getElementById(`${src}-top-state-name`).textContent = data.branch || '—';
        document.getElementById(`${src}-top-state-value`).textContent = formatAchievement(data.total);
    } catch (e) {
        console.error(`Error fetching ${source} top state:`, e);
    }
}

async function updateCPLRStats() {
    try {
        const res = await fetch(`/api/cp-lr-stats?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        const { cp_target, lr_target, combined_target, days_in_month } = data;

        document.getElementById('cp-score').textContent = `${data.cp_score || 0}%`;
        document.getElementById('lr-score').textContent = `${data.lr_score || 0}%`;
        document.getElementById('cp-update').textContent = `${data.cp_count || 0} loans`;
        document.getElementById('lr-update').textContent = `${data.lr_count || 0} loans`;

        document.getElementById('cp-progress-bar').style.width = `${data.cp_progress_pct || 0}%`;
        document.getElementById('lr-progress-bar').style.width = `${data.lr_progress_pct || 0}%`;

        const cpRR = buildRunRateText(cp_target, data.cp_total, currentMonth, currentYear, days_in_month);
        document.getElementById('cp-progress-text').textContent =
            `${data.cp_progress_pct || 0}% of ${formatAchievement(cp_target)} (${formatAchievement(data.cp_total)})${cpRR}`;

        const lrRR = buildRunRateText(lr_target, data.lr_total, currentMonth, currentYear, days_in_month);
        document.getElementById('lr-progress-text').textContent =
            `${data.lr_progress_pct || 0}% of ${formatAchievement(lr_target)} (${formatAchievement(data.lr_total)})${lrRR}`;

        document.getElementById('focus-bar').style.width = `${data.combined_progress_pct || 0}%`;
        document.getElementById('focus-text').textContent =
            `${data.combined_progress_pct || 0}% of ${formatAchievement(combined_target)} (${formatAchievement(data.combined_total)})`;
    } catch (e) {
        console.error('Error fetching CP/LR stats:', e);
    }
}

async function updateDailyGraph() {
    try {
        const res = await fetch(`/api/cp-lr-daily?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        const divisor = 100000;
        const cp = (data.cp_daily_totals || []).map(v => v / divisor);
        const lr = (data.lr_daily_totals || []).map(v => v / divisor);
        const maxValue = Math.max(...cp, ...lr) * 1.1;

        if (currentChart) currentChart.destroy();

        currentChart = new Chart(document.getElementById('dailyGraph').getContext('2d'), {
            type: 'line',
            data: {
                labels: data.days || cp.map((_, i) => i + 1),
                datasets: [
                    {
                        label: 'CP', data: cp,
                        borderColor: '#5d9cec', backgroundColor: 'rgba(93, 156, 236, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4,
                        pointBackgroundColor: '#5d9cec', pointBorderColor: '#ffffff',
                        pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6
                    },
                    {
                        label: 'LR', data: lr,
                        borderColor: '#8b5cf6', backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4,
                        pointBackgroundColor: '#8b5cf6', pointBorderColor: '#ffffff',
                        pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${formatAchievement(ctx.raw * divisor)}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(179, 189, 202, 0.2)' },
                        ticks: {
                            color: '#6c7a89',
                            callback: (v) => v >= 100 ? `${(v / 100).toFixed(2)} Cr` : `${v} L`
                        },
                        title: { display: false },
                        suggestedMax: maxValue
                    },
                    x: {
                        display: true,
                        grid: { display: false },
                        ticks: { color: '#6c7a89', maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }
                    }
                },
                layout: { padding: { bottom: 10 } }
            }
        });
    } catch (e) {
        console.error('Error fetching graph data:', e);
    }
}

async function updateAllData() {
    await Promise.all([
        updateTop3('CP', 'cp-list', 'cp-time'),
        updateTop3('LR', 'lr-list', 'lr-time'),
        updateTopState('CP'),
        updateTopState('LR'),
        updateCPLRStats(),
        updateDailyGraph(),
    ]);
}

document.addEventListener('DOMContentLoaded', () => {
    updateMonthDisplay();
    updateAllData();
    checkCelebrations(currentMonth + 1, currentYear, false);
    setInterval(() => {
        updateAllData();
        checkCelebrations(currentMonth + 1, currentYear, true);
    }, 120000);
});
