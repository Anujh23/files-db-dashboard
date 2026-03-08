// static/js/celebrations.js
// Celebration toasts for loans >= ₹1 Lakh

const SEEN_KEY = 'celebrationSeenLoans';

function _getSeenLoans() {
    try {
        return new Set(JSON.parse(sessionStorage.getItem(SEEN_KEY) || '[]'));
    } catch (_) {
        return new Set();
    }
}

function _saveSeenLoans(set) {
    try {
        sessionStorage.setItem(SEEN_KEY, JSON.stringify([...set]));
    } catch (_) {}
}

function _getContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
        c = document.createElement('div');
        c.id = 'toast-container';
        document.body.appendChild(c);
    }
    return c;
}

// Pick emoji tier based on amount
function _toastEmoji(amount) {
    if (amount >= 1000000)  return { icon: '🏆', stars: '✨💎✨' };   // 10L+
    if (amount >= 500000)   return { icon: '🔥', stars: '🌟🔥🌟' };   // 5L+
    if (amount >= 300000)   return { icon: '🚀', stars: '⭐🚀⭐' };   // 3L+
    if (amount >= 200000)   return { icon: '🎊', stars: '🎊💫🎊' };   // 2L+
    return                         { icon: '🎉', stars: '🎉✨🎉' };   // 1L+
}

// Pick a congratulatory line based on amount
function _toastLine(amount) {
    if (amount >= 1000000) return 'Absolutely crushing it! 💪';
    if (amount >= 500000)  return 'Incredible performance! 🔥';
    if (amount >= 300000)  return 'Outstanding work! 🌟';
    if (amount >= 200000)  return 'Great achievement! 🚀';
    return                        'Keep it up! 👏';
}

function showCelebrationToast(loan) {
    const container = _getContainer();
    const amount = formatAchievement(loan.loan_amount);
    const emoji = _toastEmoji(loan.loan_amount);
    const line  = _toastLine(loan.loan_amount);

    // Source badge colour
    const sourceColors = { ELI: '#5d9cec', NBL: '#8b5cf6', CP: '#f59e0b', LR: '#10b981' };
    const badgeColor = sourceColors[loan.source] || '#6c7a89';

    const toast = document.createElement('div');
    toast.className = 'celebration-toast';
    toast.innerHTML = `
        <div class="toast-confetti">${emoji.icon}</div>
        <div class="toast-body">
            <div class="toast-stars">${emoji.stars}</div>
            <div class="toast-headline">Congratulations! 🎉</div>
            <div class="toast-name">${loan.credit_by}</div>
            <div class="toast-msg">just disbursed <strong>${amount}</strong>!</div>
            <div class="toast-tagline">${line}</div>
            <div class="toast-meta">
                <span class="toast-badge" style="background:${badgeColor}">${loan.source}</span>
                <span class="toast-date">${loan.disbursal_date}</span>
            </div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;
    container.appendChild(toast);

    // Auto-remove after 7 seconds
    setTimeout(() => {
        toast.classList.add('toast-hide');
        setTimeout(() => toast.remove(), 500);
    }, 7000);
}

// Call on every data refresh. Pass notify=false on the very first load
// so existing loans don't flood with toasts.
async function checkCelebrations(month, year, notify = true) {
    try {
        const res = await fetch(`/api/recent-highlights?month=${month}&year=${year}`);
        const data = await res.json();
        const seen = _getSeenLoans();
        const newOnes = [];

        for (const h of (data.highlights || [])) {
            const key = h.loan_no || `${h.credit_by}-${h.loan_amount}-${h.disbursal_date}`;
            if (!seen.has(key)) {
                seen.add(key);
                if (notify) newOnes.push(h);
            }
        }

        _saveSeenLoans(seen);

        if (notify && newOnes.length > 0) {
            // Show up to 3 at a time so the screen isn't overwhelmed
            newOnes.slice(0, 3).forEach((h, i) => {
                setTimeout(() => showCelebrationToast(h), i * 900);
            });
        }
    } catch (e) {
        console.error('celebrations check error', e);
    }
}

// ── TEST FUNCTION ────────────────────────────────────────
// Called by the test button. Shows fake toasts across all sources.
function testCelebrations() {
    const today = new Date().toISOString().split('T')[0];
    const samples = [
        { credit_by: 'Amit Sharma',      loan_amount: 1250000, source: 'ELI', disbursal_date: today },
        { credit_by: 'Priya Mehta',      loan_amount: 350000,  source: 'NBL', disbursal_date: today },
        { credit_by: 'Chitranshi Singh', loan_amount: 550000,  source: 'LR',  disbursal_date: today },
        { credit_by: 'Ravi Kumar',       loan_amount: 200000,  source: 'CP',  disbursal_date: today },
    ];
    samples.forEach((s, i) => {
        s.loan_no = `TEST-${Date.now()}-${i}`;
        setTimeout(() => showCelebrationToast(s), i * 900);
    });
}
