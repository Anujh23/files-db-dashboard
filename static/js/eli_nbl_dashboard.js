// static/js/dashboard.js
let currentChart = null;
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();

async function updateELIData() {
    try {
        const res = await fetch(`/api/eli-top3?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        const eliList = document.getElementById('eli-list');
        eliList.innerHTML = '';
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
        updateTimeDisplay('eli-time');
    } catch (error) {
        console.error('Error fetching ELI data:', error);
        document.getElementById('eli-list').innerHTML = '<li class="top-item">Error loading data</li>';
    }
}

async function updateELITopState() {
    try {
        const res = await fetch(`/api/eli-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        document.getElementById('eli-top-state-name').textContent = data.branch || '—';
        document.getElementById('eli-top-state-value').textContent = formatAchievement(data.total);
    } catch (err) {
        console.error('ELI Top Branch error', err);
        document.getElementById('eli-top-state-name').textContent = '—';
        document.getElementById('eli-top-state-value').textContent = '₹0';
    }
}

async function updateNBLData() {
    try {
        const res = await fetch(`/api/nbl-top3?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        const nblList = document.getElementById('nbl-list');
        nblList.innerHTML = '';
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
        updateTimeDisplay('nbl-time');
    } catch (error) {
        console.error('Error fetching NBL data:', error);
        document.getElementById('nbl-list').innerHTML = '<li class="top-item">Error loading data</li>';
    }
}

async function updateNBLTopState() {
    try {
        const res = await fetch(`/api/nbl-top-state?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        document.getElementById('nbl-top-state-name').textContent = data.branch || '—';
        document.getElementById('nbl-top-state-value').textContent = formatAchievement(data.total);
    } catch (err) {
        console.error('NBL Top Branch error', err);
        document.getElementById('nbl-top-state-name').textContent = '—';
        document.getElementById('nbl-top-state-value').textContent = '₹0';
    }
}

async function updateDashboardStats() {
    try {
        const res = await fetch(`/api/dashboard-stats?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        const { eli_target, nbl_target, combined_target, days_in_month } = data;

        document.getElementById('eli-score').textContent = `${data.eli_score}%`;
        document.getElementById('eli-update').textContent = `${data.eli_count} loans`;
        document.getElementById('eli-progress-bar').style.width = `${data.eli_progress_pct}%`;
        const eliRR = buildRunRateText(eli_target, data.eli_total, currentMonth, currentYear, days_in_month);
        document.getElementById('eli-progress-text').textContent =
            `${data.eli_progress_pct}% of ${formatAchievement(eli_target)} (${formatAchievement(data.eli_total)})${eliRR}`;

        document.getElementById('nbl-score').textContent = `${data.nbl_score}%`;
        document.getElementById('nbl-update').textContent = `${data.nbl_count} loans`;
        document.getElementById('nbl-progress-bar').style.width = `${data.nbl_progress_pct}%`;
        const nblRR = buildRunRateText(nbl_target, data.nbl_total, currentMonth, currentYear, days_in_month);
        document.getElementById('nbl-progress-text').textContent =
            `${data.nbl_progress_pct}% of ${formatAchievement(nbl_target)} (${formatAchievement(data.nbl_total)})${nblRR}`;

        document.getElementById('focus-bar').style.width = `${data.leader_progress_pct}%`;
        document.getElementById('focus-text').textContent =
            `${data.leader_progress_pct}% of ${formatAchievement(combined_target)} (${formatAchievement(data.combined_total)})`;

        document.querySelector('.welcome-text').textContent =
            `Current Month Dashboard • ${new Date().toLocaleTimeString('en-IN', { hour12: true, hour: '2-digit', minute: '2-digit' })}`;
    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
    }
}

async function updateDailyGraph() {
    try {
        const res = await fetch(`/api/daily-performance?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        const graphDivisor = 100000;
        const eliData = data.eli_daily_totals.map(v => v / graphDivisor);
        const nblData = data.nbl_daily_totals.map(v => v / graphDivisor);
        const maxValue = Math.max(...eliData, ...nblData) * 1.1;

        if (currentChart) currentChart.destroy();

        currentChart = new Chart(document.getElementById('dailyGraph').getContext('2d'), {
            type: 'line',
            data: {
                labels: data.days || eliData.map((_, i) => `Day ${i + 1}`),
                datasets: [
                    {
                        label: 'ELI', data: eliData,
                        borderColor: '#5d9cec', backgroundColor: 'rgba(93, 156, 236, 0.1)',
                        borderWidth: 2, fill: true, tension: 0.4,
                        pointBackgroundColor: '#5d9cec', pointBorderColor: '#ffffff',
                        pointBorderWidth: 2, pointRadius: 4, pointHoverRadius: 6
                    },
                    {
                        label: 'NBL', data: nblData,
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
                            label: (ctx) => `${ctx.dataset.label}: ${formatAchievement(ctx.raw * graphDivisor)}`
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
    } catch (error) {
        console.error('Error fetching graph data:', error);
    }
}

async function updateAllData() {
    await Promise.all([
        updateELIData(),
        updateNBLData(),
        updateDashboardStats(),
        updateDailyGraph(),
        updateELITopState(),
        updateNBLTopState()
    ]);
}

document.addEventListener('DOMContentLoaded', () => {
    updateMonthDisplay();
    updateAllData();
    checkCelebrations(currentMonth + 1, currentYear, false);
    setInterval(() => {
        updateAllData();
        checkCelebrations(currentMonth + 1, currentYear, true);
    }, 30000);
});
