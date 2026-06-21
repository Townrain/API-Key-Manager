/**
 * Batch check results module.
 * Extracted from templates/index.html ~line 4007.
 */

import { State } from './state.js';
import { translateError, translateErrorType } from './utils.js';

export function showBatchResults(data, hintEl) {
    const resultsEl = document.getElementById('batch-results');
    const results = data.results || [];
    const validCount = results.filter(r => r.status === 'valid').length;
    const invalidCount = results.filter(r => r.status === 'invalid').length;
    const errorCount = results.filter(r => r.status === 'error').length;
    hintEl.textContent = `${results.length} 个完成: ${validCount} 有效, ${invalidCount} 无效, ${errorCount} 错误`;

    if (results.length === 0) {
        resultsEl.innerHTML = '<div style="padding: 16px; color: var(--text-dim); text-align: center;">无检测结果</div>';
        return;
    }

    resultsEl.innerHTML = `<div class="batch-summary"><span class="valid">✓ ${validCount} 有效</span><span class="invalid">✗ ${invalidCount} 无效</span><span class="error">⚠ ${errorCount} 错误</span></div>` + results.map((r, i) => {
        const badgeClass = r.status === 'valid' ? 'badge-valid' : r.status === 'invalid' ? 'badge-invalid' : 'badge-error';
        const badgeText = State.STATUS_MAP[r.status] || r.status;
        const te = translateError(r.error || '');
        const teType = translateErrorType(r.error_type || '');
        return `<div class="batch-result-item" style="animation-delay: ${i * 0.03}s">
                    <span class="batch-result-key">${r.key_masked || r.key || '-'}</span>
                    <span class="badge ${badgeClass}" style="padding: 3px 10px; font-size: 11px;">${badgeText}</span>
                    ${teType ? `<span class="batch-result-error" title="${teType}" style="color: var(--neon-amber);">${teType}</span>` : ''}
                    ${r.error ? `<span class="batch-result-error" title="${r.error}">${te || r.error}</span>` : ''}
                </div>`;
    }).join('');

    // Lazy import to avoid circular dependency
    import('./api/index.js').then(api => { api.loadStats(); api.loadKeys(); });
}
