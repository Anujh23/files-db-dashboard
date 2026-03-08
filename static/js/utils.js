// static/js/utils.js
// Shared utilities used by both dashboard.js and cp_lr_dashboard.js

const monthNames = ["January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"];

function formatNumberIndian(num) {
    if (!num) return '0';
    let numStr = num.toString();
    let lastThree = numStr.substring(numStr.length - 3);
    let otherNumbers = numStr.substring(0, numStr.length - 3);
    if (otherNumbers !== '') lastThree = ',' + lastThree;
    return otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;
}

function formatNumber(num) {
    return formatNumberIndian(num);
}

function formatAchievement(value) {
    if (!value) return '₹0';
    if (value >= 10000000) return '₹' + (value / 10000000).toFixed(2) + ' Cr';
    if (value >= 100000)   return '₹' + (value / 100000).toFixed(2) + ' L';
    if (value >= 1000)     return '₹' + (value / 1000).toFixed(0) + 'K';
    return '₹' + formatNumberIndian(value);
}

function updateTimeDisplay(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = 'Updated: ' + new Date().toLocaleTimeString('en-US', {
        hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

function updateMonthDisplay() {
    const el = document.getElementById('current-month');
    if (el) el.textContent = `${monthNames[currentMonth]} ${currentYear}`;
}

function changeMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 11) { currentMonth = 0; currentYear++; }
    else if (currentMonth < 0) { currentMonth = 11; currentYear--; }
    updateMonthDisplay();
    updateAllData();
}

function buildRunRateText(target, total, month, year, daysInMonth) {
    const today = new Date();
    if (month !== today.getMonth() || year !== today.getFullYear()) return '';
    const daysLeft = daysInMonth - today.getDate() + 1;
    const remaining = target - total;
    if (remaining <= 0) return ' · Target achieved!';
    return ` · Need ${formatAchievement(remaining / daysLeft)}/day (${daysLeft}d left)`;
}
