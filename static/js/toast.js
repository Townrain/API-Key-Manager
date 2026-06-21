/**
 * Toast notification module.
 * Extracted from templates/index.html ~line 3883.
 */

export function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast');
    toast.className = `toast ${type} show`;
    const icons = { success: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>', error: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>', info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>' };
    toast.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${icons[type]}</svg><span>${msg}</span>`;
    setTimeout(() => toast.classList.remove('show'), 4000);
}
