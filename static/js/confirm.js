/**
 * Custom confirm modal module.
 * Extracted from templates/index.html ~line 3172.
 */

let confirmCallback = null;

export function showConfirm({ title, message, icon = 'danger', okText = '确定', onConfirm }) {
    const iconSvgs = {
        danger: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        warning: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
        success: '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
    };

    document.getElementById('confirm-icon').innerHTML = `<div class="confirm-icon-wrap ${icon}">${iconSvgs[icon] || iconSvgs.danger}</div>`;
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-message').textContent = message;
    const okBtn = document.getElementById('confirm-ok-btn');
    okBtn.textContent = okText;
    okBtn.className = icon === 'danger' ? 'btn-primary' : 'btn-primary';
    okBtn.style.background = icon === 'danger'
        ? 'linear-gradient(135deg, var(--neon-red), #cc2255)'
        : 'linear-gradient(135deg, var(--neon-cyan), #00c8d4)';
    confirmCallback = onConfirm;
    document.getElementById('confirm-modal').classList.add('show');
}

export function confirmOk() {
    document.getElementById('confirm-modal').classList.remove('show');
    if (confirmCallback) confirmCallback();
    confirmCallback = null;
}

export function confirmCancel() {
    document.getElementById('confirm-modal').classList.remove('show');
    confirmCallback = null;
}
