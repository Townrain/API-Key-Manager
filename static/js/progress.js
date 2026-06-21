/**
 * Progress overlay module.
 * Extracted from templates/index.html ~line 3809.
 */

export function showProgress(title, sub) {
    document.getElementById('progress-title').textContent = title;
    document.getElementById('progress-subtitle').textContent = sub;
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-current').textContent = '0';
    document.getElementById('progress-total').textContent = '0';
    document.getElementById('progress-percent').textContent = '0%';
    document.getElementById('progress-overlay').classList.add('active');
}

export function updateProgress(cur, total) {
    const pct = total > 0 ? Math.round((cur / total) * 100) : 0;
    document.getElementById('progress-bar').style.width = `${pct}%`;
    document.getElementById('progress-current').textContent = cur;
    document.getElementById('progress-total').textContent = total;
    document.getElementById('progress-percent').textContent = `${pct}%`;
}

export function hideProgress() {
    document.getElementById('progress-overlay').classList.remove('active');
}
