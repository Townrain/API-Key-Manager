/**
 * Keys table rendering and pagination module.
 * Extracted from templates/index.html ~lines 3002-3141.
 */

import { State } from './state.js';
import { esc, escAttr, translateError, translateErrorType } from './utils.js';
import { showToast } from './toast.js';

// Re-export loadKeys from api.js to avoid circular dependency
// (api.js uses lazy import of this module, so we cannot import from api.js here)

// Search debounce
let searchTimer = null;

export function filterKeys() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
        State.searchQuery = (document.getElementById('search-input').value || '').toLowerCase().trim();
        renderKeys();
    }, 150);
}

export function renderKeys() {
    let fk = State.allKeys;
    if (State.searchQuery) fk = fk.filter(k => k.key.toLowerCase().includes(State.searchQuery) || k.key_masked.toLowerCase().includes(State.searchQuery) || k.provider.toLowerCase().includes(State.searchQuery));

    const tbody = document.getElementById('keys-table');
    document.getElementById('table-title').textContent = `${State.TAB_TITLES[State.currentTab]} (第${State.currentPage}页, 共${State.totalCount}条)`;

    if (fk.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M15 7a2 2 0 0 1 2 2m4 0a6 6 0 0 1-7.743 5.743L11 17H9v2H7v2H4a1 1 0 0 1-1-1v-2.586a1 1 0 0 1 .293-.707l5.964-5.964A6 6 0 1 1 21 9z"/></svg><h3>暂无数据</h3><p>当前筛选条件下没有 Key</p></div></td></tr>';
        updatePagination();
        return;
    }

    tbody.innerHTML = fk.map((k, idx) => {
        const dk = State.showFullKeys ? k.key : k.key_masked;
        const models = k.models || [];
        let md = '';
        if (models.length > 0) {
            const mm = models.slice(0, 3);
            const rem = models.length - 3;
            md = `<div class="models-wrap"><div class="models-tags">${mm.map(m => `<span class="model-chip">${m.length > 15 ? m.split('/').pop().substring(0, 12) + '...' : m}</span>`).join('')}${rem > 0 ? `<span class="model-chip more" onclick="showModelsModal('${escAttr(k.key_masked)}', ${JSON.stringify(models).replace(/&/g,'&amp;').replace(/"/g, '&quot;')})">+${rem}</span>` : ''}</div></div>`;
        } else {
            md = '<span style="font-size: 13px; color: var(--text-ghost);">-</span>';
        }

        const te = translateError(k.last_error || '');
        const sd = k.status === 'valid'
            ? `<span class="badge badge-valid">有效</span>`
            : `<div class="error-group">
                        <span class="badge badge-${k.status}">${State.STATUS_MAP[k.status] || k.status}</span>
                        ${k.last_error ? `<span class="error-hint" title="${te ? te + ' (' + k.last_error + ')' : k.last_error}${k.error_type ? ' [' + translateErrorType(k.error_type) + ']' : ''}"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span class="error-text">${te || k.last_error}${k.error_type ? ' <span style="color:var(--neon-amber);font-size:11px;">[' + translateErrorType(k.error_type) + ']</span>' : ''}</span></span>` : ''}
                    </div>`;

        return `<tr style="animation: fadeInRow 0.3s ease ${idx * 0.02}s both;">
                    <td><div class="key-cell" onclick="copyKey('${escAttr(k.key)}')" title="点击复制">${dk}</div></td>
                    <td><span class="provider-chip" onclick="showProviderDetail('${escAttr(k.provider)}')" style="cursor: pointer;" title="点击查看服务商详情">${State.DISPLAY_NAMES[k.provider] || k.provider}</span></td>
                    <td>${sd}</td>
                    <td>${md}</td>
                    <td style="font-size: 12px; color: var(--text-dim);">${k.last_checked ? new Date(k.last_checked).toLocaleString('zh-CN') : '-'}</td>
                    <td style="font-family: 'Fira Code', monospace; font-size: 12px;">${k.tests.max_tokens ? (k.tests.max_tokens >= 1000000 ? (k.tests.max_tokens/1000000).toFixed(1)+'M' : k.tests.max_tokens >= 1000 ? (k.tests.max_tokens/1000)+'K' : k.tests.max_tokens) : '-'}</td>
                    <td style="font-family: 'Fira Code', monospace; font-size: 12px;">${k.tests.max_concurrency || '-'}</td>
                    <td style="font-family: 'Fira Code', monospace; font-size: 12px; color: var(--text-dim);">${k.balance && k.balance.balance != null ? k.balance.balance + ' ' + (k.balance.currency || '') : '-'}</td>
                </tr>`;
    }).join('');
    updatePagination();
}

export function updatePagination() {
    const bar = document.getElementById('pagination-bar');
    const sizes = [25, 50, 100, 200];
    const sizeOpts = sizes.map(s => `<option value="${s}" ${s === State.pageSize ? 'selected' : ''}>${s} 条/页</option>`).join('');
    const navHtml = State.totalPages > 1
        ? `<button onclick="goToPage(${State.currentPage - 1})" ${State.currentPage <= 1 ? 'disabled' : ''}>«</button><span class="page-info">${State.currentPage} / ${State.totalPages}</span><button onclick="goToPage(${State.currentPage + 1})" ${State.currentPage >= State.totalPages ? 'disabled' : ''}>»</button>`
        : '<span class="page-info">1 / 1</span>';
    bar.innerHTML = `<select onchange="changePageSize(this.value)" style="background:var(--surface-2);color:var(--text-primary);border:1px solid var(--border-subtle);padding:6px 10px;border-radius:6px;font-family:'Fira Code',monospace;font-size:12px;cursor:pointer">${sizeOpts}</select><span class="page-info">共 ${State.totalCount} 条</span>${navHtml}`;
}

export function changePageSize(size) {
    State.pageSize = parseInt(size);
    State.currentPage = 1;
    import('./api/keys.js').then(api => api.loadKeys(1));
}

export function goToPage(page) {
    if (page >= 1 && page <= State.totalPages) {
        import('./api/keys.js').then(api => api.loadKeys(page));
    }
}

export function switchTab(tab) {
    State.currentTab = tab;
    State.currentPage = 1;
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    const targetTab = document.querySelector(`[data-tab="${tab}"]`);
    import('./api/keys.js').then(api => api.loadKeys(1));
}

export function toggleKeyDisplay() {
    State.showFullKeys = !State.showFullKeys;
    document.getElementById('show-key-toggle').classList.toggle('active');
    renderKeys();
}

export function copyKey(key) {
    navigator.clipboard.writeText(key).then(() => showToast('已复制到剪贴板', 'success'));
}
