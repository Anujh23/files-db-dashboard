// static/js/all_products_dashboard.js
// All four products (ELI, NBL, CP, LR) on a single page.

let currentChart = null;
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();

const PRODUCT_COLORS = {
    ELI: '#5d9cec',  // blue
    NBL: '#8b5cf6',  // purple (kept from existing page)
    CP:  '#0ea5e9',  // sky blue
    LR:  '#1e40af',  // deep navy blue
};

async function updateAllStats() {
    try {
        const res = await fetch(`/api/all-stats?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();
        const days_in_month = data.days_in_month;

        ['eli', 'nbl', 'cp', 'lr'].forEach(key => {
            const score = data[`${key}_score`] || 0;
            const pct = data[`${key}_progress_pct`] || 0;
            const total = data[`${key}_total`] || 0;
            const target = data[`${key}_target`] || 0;
            const count = data[`${key}_count`] || 0;

            document.getElementById(`${key}-score`).textContent = `${score}%`;
            document.getElementById(`${key}-update`).textContent = `${count} loans`;
            document.getElementById(`${key}-progress-bar`).style.width = `${pct}%`;
            const rr = buildRunRateText(target, total, currentMonth, currentYear, days_in_month);
            document.getElementById(`${key}-progress-text`).textContent =
                `${pct}% of ${formatAchievement(target)} (${formatAchievement(total)})${rr}`;
        });

        document.getElementById('focus-bar').style.width = `${data.combined_progress_pct || 0}%`;
        document.getElementById('focus-text').textContent =
            `${data.combined_progress_pct || 0}% of ${formatAchievement(data.combined_target)} (${formatAchievement(data.combined_total)})`;
    } catch (e) {
        console.error('Error fetching all stats:', e);
    }
}

function buildDataset(label, values, color) {
    return {
        label,
        data: values,
        borderColor: color,
        backgroundColor: color + '1a',  // ~10% alpha overlay fill under the line
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointBackgroundColor: color,
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointRadius: 3,
        pointHoverRadius: 6,
    };
}

async function updateDailyGraph() {
    try {
        const res = await fetch(`/api/all-daily?month=${currentMonth + 1}&year=${currentYear}`);
        const data = await res.json();

        const divisor = 100000;
        const eli = (data.eli_daily_totals || []).map(v => v / divisor);
        const nbl = (data.nbl_daily_totals || []).map(v => v / divisor);
        const cp  = (data.cp_daily_totals  || []).map(v => v / divisor);
        const lr  = (data.lr_daily_totals  || []).map(v => v / divisor);
        const maxValue = Math.max(...eli, ...nbl, ...cp, ...lr, 0) * 1.1;

        if (currentChart) currentChart.destroy();

        currentChart = new Chart(document.getElementById('dailyGraph').getContext('2d'), {
            type: 'line',
            data: {
                labels: data.days || eli.map((_, i) => i + 1),
                datasets: [
                    buildDataset('ELI', eli, PRODUCT_COLORS.ELI),
                    buildDataset('NBL', nbl, PRODUCT_COLORS.NBL),
                    buildDataset('CP',  cp,  PRODUCT_COLORS.CP),
                    buildDataset('LR',  lr,  PRODUCT_COLORS.LR),
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
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
        updateAllStats(),
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
