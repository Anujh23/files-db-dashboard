// static/js/all_products_dashboard.js
// Rotator: ALL → ELI → NBL → CP → LR

let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();

const PRODUCT_COLORS = {
    ELI: '#5d9cec',
    NBL: '#8b5cf6',
    CP:  '#0ea5e9',
    LR:  '#1e40af',
};

const PRODUCT_FULLNAMES = {
    ELI: 'Everyday Loan India',
    NBL: 'Next Big Loan',
    CP:  'Credit Pay',
    LR:  'Lending Rupee',
};

const VIEWS = ['ALL', 'ELI', 'NBL', 'CP', 'LR'];
const ROTATION_INTERVAL_MS = 10000;
const FADE_MS = 350;

let currentViewIdx = 0;
let rotationTimer = null;
let isPaused = false;

let allChart = null;
let productChart = null;

const statsCache = {};
const dailyCache = { days: [], eli: [], nbl: [], cp: [], lr: [] };
const leadersCache = {};

// ── Data fetch ──────────────────────────────────────────────

async function fetchStatsAndDaily() {
    const [stats, daily] = await Promise.all([
        fetch(`/api/all-stats?month=${currentMonth + 1}&year=${currentYear}`).then(r => r.json()),
        fetch(`/api/all-daily?month=${currentMonth + 1}&year=${currentYear}`).then(r => r.json()),
    ]);
    Object.assign(statsCache, stats);
    dailyCache.days = daily.days || [];
    dailyCache.eli = daily.eli_daily_totals || [];
    dailyCache.nbl = daily.nbl_daily_totals || [];
    dailyCache.cp  = daily.cp_daily_totals  || [];
    dailyCache.lr  = daily.lr_daily_totals  || [];
}

async function fetchLeaders() {
    const products = ['ELI', 'NBL', 'CP', 'LR'];
    const results = await Promise.all(products.map(async p => {
        const src = p.toLowerCase();
        const [t3, br] = await Promise.all([
            fetch(`/api/${src}-top3?month=${currentMonth + 1}&year=${currentYear}&limit=5`).then(r => r.json()),
            fetch(`/api/${src}-top-state?month=${currentMonth + 1}&year=${currentYear}`).then(r => r.json()),
        ]);
        return {
            top3: t3.top3 || [],
            branch: { name: br.branch || '—', total: br.total || 0 },
        };
    }));
    products.forEach((p, i) => leadersCache[p] = results[i]);
}

async function refreshAll() {
    await Promise.all([fetchStatsAndDaily(), fetchLeaders()]);
}

// ── ALL view ────────────────────────────────────────────────

function buildDataset(label, values, color) {
    return {
        label,
        data: values,
        borderColor: color,
        backgroundColor: color + '1a',
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

function chartOptions(divisor, maxValue) {
    return {
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
                suggestedMax: maxValue
            },
            x: {
                display: true,
                grid: { display: false },
                ticks: { color: '#6c7a89', maxRotation: 0, autoSkip: true, maxTicksLimit: 15 }
            }
        },
        layout: { padding: { bottom: 10 } }
    };
}

function renderAllView() {
    const data = statsCache;
    if (!data || data.days_in_month === undefined) return;
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

    const divisor = 100000;
    const eli = dailyCache.eli.map(v => v / divisor);
    const nbl = dailyCache.nbl.map(v => v / divisor);
    const cp  = dailyCache.cp.map(v => v / divisor);
    const lr  = dailyCache.lr.map(v => v / divisor);
    const maxValue = Math.max(...eli, ...nbl, ...cp, ...lr, 0) * 1.1;

    const canvas = document.getElementById('dailyGraph');
    if (!canvas) return;
    if (allChart) allChart.destroy();
    allChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: dailyCache.days.length ? dailyCache.days : eli.map((_, i) => i + 1),
            datasets: [
                buildDataset('ELI', eli, PRODUCT_COLORS.ELI),
                buildDataset('NBL', nbl, PRODUCT_COLORS.NBL),
                buildDataset('CP',  cp,  PRODUCT_COLORS.CP),
                buildDataset('LR',  lr,  PRODUCT_COLORS.LR),
            ]
        },
        options: chartOptions(divisor, maxValue)
    });
}

// ── Product view ────────────────────────────────────────────

function renderProductView(product) {
    const key = product.toLowerCase();
    const data = statsCache;
    const leaders = leadersCache[product];
    if (!data || !leaders) return;

    const view = document.getElementById('view-product');
    view.dataset.product = product;

    const target = data[`${key}_target`] || 0;
    const total = data[`${key}_total`] || 0;
    const pct = data[`${key}_progress_pct`] || 0;
    const count = data[`${key}_count`] || 0;

    document.getElementById('prod-title').textContent = product;
    document.getElementById('prod-fullname').textContent = PRODUCT_FULLNAMES[product] || '';
    document.getElementById('prod-target').textContent = formatAchievement(target);
    document.getElementById('prod-achieved').textContent = formatAchievement(total);
    document.getElementById('prod-pct').textContent = `${pct}%`;
    document.getElementById('prod-count').textContent = `${count}`;

    const list = document.getElementById('prod-leaders');
    list.innerHTML = '';
    const items = (leaders.top3 || []).slice(0, 5);
    if (!items.length) {
        const li = document.createElement('li');
        li.className = 'leaders-empty';
        li.textContent = 'No data yet';
        list.appendChild(li);
    } else {
        items.forEach((item, idx) => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span class="product-rank">${idx + 1}</span>
                <span class="leader-name">${item.CM_Name}</span>
                <span class="leader-val">${formatAchievement(item.Achievement)}</span>
            `;
            list.appendChild(li);
        });
    }

    document.getElementById('prod-branch-name').textContent = leaders.branch.name;
    document.getElementById('prod-branch-val').textContent = formatAchievement(leaders.branch.total);

    const divisor = 100000;
    const series = (dailyCache[key] || []).map(v => v / divisor);
    const maxValue = Math.max(...series, 0) * 1.1 || 1;
    const color = PRODUCT_COLORS[product];

    const canvas = document.getElementById('productGraph');
    if (!canvas) return;
    if (productChart) productChart.destroy();
    productChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: dailyCache.days.length ? dailyCache.days : series.map((_, i) => i + 1),
            datasets: [buildDataset(product, series, color)]
        },
        options: chartOptions(divisor, maxValue)
    });
}

// ── View switching ──────────────────────────────────────────

function showView(viewName, withFade = true) {
    const stage = document.getElementById('rotator-stage');
    const allEl = document.getElementById('view-all');
    const prodEl = document.getElementById('view-product');
    const rotator = document.getElementById('rotator');

    const apply = () => {
        if (viewName === 'ALL') {
            allEl.hidden = false;
            prodEl.hidden = true;
            rotator.style.removeProperty('--accent');
            renderAllView();
        } else {
            allEl.hidden = true;
            prodEl.hidden = false;
            rotator.style.setProperty('--accent', PRODUCT_COLORS[viewName]);
            renderProductView(viewName);
        }

        document.querySelectorAll('.rotator-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.view === viewName);
        });

        const fill = document.getElementById('rotator-progress-fill');
        fill.classList.remove('run');
        void fill.offsetWidth;
        if (!isPaused) fill.classList.add('run');

        if (withFade) {
            requestAnimationFrame(() => stage.classList.remove('fading'));
        }
    };

    if (withFade) {
        stage.classList.add('fading');
        setTimeout(apply, FADE_MS);
    } else {
        apply();
    }
}

function startRotation() {
    if (rotationTimer) clearInterval(rotationTimer);
    rotationTimer = setInterval(() => {
        if (isPaused) return;
        currentViewIdx = (currentViewIdx + 1) % VIEWS.length;
        showView(VIEWS[currentViewIdx], true);
    }, ROTATION_INTERVAL_MS);
}

function jumpTo(viewName) {
    const idx = VIEWS.indexOf(viewName);
    if (idx < 0) return;
    currentViewIdx = idx;
    showView(viewName, true);
    startRotation();
}

function togglePause() {
    isPaused = !isPaused;
    const btn = document.getElementById('rotator-pause');
    btn.textContent = isPaused ? '▶' : '⏸';
    const fill = document.getElementById('rotator-progress-fill');
    if (isPaused) {
        fill.classList.remove('run');
    } else {
        fill.classList.remove('run');
        void fill.offsetWidth;
        fill.classList.add('run');
    }
}

function bindRotatorControls() {
    document.querySelectorAll('.rotator-tab').forEach(tab => {
        tab.addEventListener('click', () => jumpTo(tab.dataset.view));
    });
    document.getElementById('rotator-pause').addEventListener('click', togglePause);
}

// ── Boot ────────────────────────────────────────────────────

async function updateAllData() {
    await refreshAll();
    showView(VIEWS[currentViewIdx], false);
}

document.addEventListener('DOMContentLoaded', () => {
    updateMonthDisplay();
    bindRotatorControls();
    updateAllData().then(() => startRotation());
    checkCelebrations(currentMonth + 1, currentYear, false);
    setInterval(() => {
        updateAllData();
        checkCelebrations(currentMonth + 1, currentYear, true);
    }, 120000);
});
