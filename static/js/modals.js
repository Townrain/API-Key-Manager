/**
 * Modal dialogs module.
 * Extracted from templates/index.html ~lines 3152-3168, 3012-3014, 3967-3977, 4114-4315.
 */

import { State } from './state.js';
import { safeFetch } from './api/client.js';
import { showToast } from './toast.js';

// ─── Export Modal ────────────────────────────────────────────────────────────

export function closeModal() {
    document.getElementById('export-modal').classList.remove('show');
}

export function copyExport() {
    const ta = document.getElementById('export-text');
    ta.select();
    navigator.clipboard.writeText(ta.value).then(() => showToast('已复制', 'success'));
}

export function downloadExport() {
    const text = document.getElementById('export-text').value;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `valid_keys_${new Date().toISOString().slice(0,10)}.txt`; a.click();
    URL.revokeObjectURL(url);
    showToast('下载已开始', 'success');
}

// ─── Models Modal ────────────────────────────────────────────────────────────

export function showModelsModal(name, models) {
    document.getElementById('models-modal-title').textContent = `${name} - 模型 (${models.length})`;
    document.getElementById('models-list').innerHTML = models.map((m, i) => `<div style="display: flex; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 8px; transition: all 0.2s; animation: fadeInRow 0.2s ease ${i * 0.02}s both;" onmouseover="this.style.background='var(--surface-2)'" onmouseout="this.style.background=''"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--neon-cyan)" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/></svg><span style="flex: 1; font-family: 'Fira Code', monospace; font-size: 12px;">${m}</span><button onclick="copyKey('${m}')" style="background: none; border: 1px solid var(--border-subtle); color: var(--text-dim); padding: 4px; border-radius: 4px; cursor: pointer; display: flex; opacity: 0.5;" onmouseover="this.style.opacity=1; this.style.borderColor='var(--neon-cyan)'" onmouseout="this.style.opacity=0.5; this.style.borderColor='var(--border-subtle)'"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button></div>`).join('');
    document.getElementById('models-modal').classList.add('show');
}

export function closeModelsModal() {
    document.getElementById('models-modal').classList.remove('show');
}

// ─── Shortcuts Modal ─────────────────────────────────────────────────────────

export function showShortcutsModal() {
    document.getElementById('shortcuts-modal').classList.add('show');
}

export function closeShortcutsModal() {
    document.getElementById('shortcuts-modal').classList.remove('show');
}

// ─── Signature Report Modal ──────────────────────────────────────────────────

export async function showSignatureReport() {
    const body = document.getElementById('signature-report-body');
    body.innerHTML = '<div class="sig-no-data"><div class="progress-spinner" style="width: 32px; height: 32px; margin: 0 auto 16px;"></div>加载签名验证报告...</div>';
    document.getElementById('signature-report-modal').classList.add('show');

    try {
        const report = await safeFetch('/api/signature-report');
        renderSignatureReport(report);
    } catch (e) {
        body.innerHTML = `<div class="sig-no-data" style="color: var(--neon-red);">加载失败: ${e.message}</div>`;
    }
}

export function closeSignatureReportModal() {
    document.getElementById('signature-report-modal').classList.remove('show');
}

export function renderSignatureReport(report) {
    const body = document.getElementById('signature-report-body');
    const summary = report.summary || {};
    const results = report.results || [];

    const generatedAt = report.generated_at ? new Date(report.generated_at).toLocaleString('zh-CN') : '未知';

    // Summary cards
    const summaryHtml = `
        <div class="sig-report-container">
            <div style="font-family: 'Fira Code', monospace; font-size: 12px; color: var(--text-ghost); margin-bottom: 16px;">生成时间: ${generatedAt}</div>
            <div class="sig-summary-grid">
                <div class="sig-summary-card cyan">
                    <div class="sig-val">${summary.total_providers || 0}</div>
                    <div class="sig-label">总提供商</div>
                </div>
                <div class="sig-summary-card green">
                    <div class="sig-val">${summary.successful_tests || 0}</div>
                    <div class="sig-label">成功测试</div>
                </div>
                <div class="sig-summary-card blue">
                    <div class="sig-val">${summary.full_match || 0}</div>
                    <div class="sig-label">完全匹配</div>
                </div>
                <div class="sig-summary-card amber">
                    <div class="sig-val">${summary.partial_match || 0}</div>
                    <div class="sig-label">部分匹配</div>
                </div>
                <div class="sig-summary-card red">
                    <div class="sig-val">${summary.no_match || 0}</div>
                    <div class="sig-label">无匹配</div>
                </div>
                <div class="sig-summary-card magenta">
                    <div class="sig-val">${summary.has_conflicts || 0}</div>
                    <div class="sig-label">冲突数</div>
                </div>
                <div class="sig-summary-card purple">
                    <div class="sig-val">${summary.has_new_signatures || 0}</div>
                    <div class="sig-label">新发现签名</div>
                </div>
            </div>`;

    // Results table
    let tableHtml = `
            <div class="sig-detail-section">
                <div class="sig-section-title">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>
                    提供商详情
                    <span class="count-badge">${results.length}</span>
                </div>
                <div class="sig-detail-content">
                    <table class="sig-table">
                        <thead><tr>
                            <th>提供商</th>
                            <th>状态</th>
                            <th>匹配率</th>
                            <th>已匹配</th>
                            <th>缺失</th>
                            <th>新签名</th>
                            <th>冲突</th>
                        </tr></thead>
                        <tbody>`;

    results.forEach(r => {
        const es = r.test_result || {};
        const unique = r.unique_signatures || {};
        const newSigs = r.new_signatures || [];
        const conflicts = r.conflicts || [];

        // Determine status
        let statusClass = 'ok';
        let statusText = 'OK';
        if (es.error === 'timeout') { statusClass = 'timeout'; statusText = '超时'; }
        else if (es.error || !es.valid) { statusClass = 'error'; statusText = es.error || '错误'; }

        // Match rate
        const rate = unique.match_rate != null ? unique.match_rate : 0;
        const ratePct = Math.round(rate * 100);
        const rateClass = rate >= 0.8 ? 'high' : rate >= 0.3 ? 'mid' : 'low';

        // Tags
        const matchedTags = (unique.matched || []).map(s => `<span class="sig-tag matched">${s}</span>`).join('');
        const missingTags = (unique.missing || []).map(s => `<span class="sig-tag missing">${s}</span>`).join('');
        const newTags = newSigs.slice(0, 5).map(s => `<span class="sig-tag new-sig">${s}</span>`).join('') + (newSigs.length > 5 ? `<span class="sig-tag new-sig">+${newSigs.length - 5}</span>` : '');
        const conflictTags = conflicts.map(c => `<span class="sig-tag conflict">${c.signature} → ${c.other_provider}</span>`).join('');

        tableHtml += `
                    <tr>
                        <td><span style="font-weight: 600; color: var(--text-primary);">${r.provider}</span></td>
                        <td><span class="sig-status-badge ${statusClass}">${statusText}</span></td>
                        <td>
                            <div class="sig-match-rate">
                                <span style="font-family: 'Fira Code', monospace; font-size: 12px; color: ${rateClass === 'high' ? 'var(--neon-green)' : rateClass === 'mid' ? 'var(--neon-amber)' : 'var(--neon-red)'};">${ratePct}%</span>
                                <div class="sig-match-bar"><div class="sig-match-bar-fill ${rateClass}" style="width: ${ratePct}%;"></div></div>
                            </div>
                        </td>
                        <td>${matchedTags || '<span style="color: var(--text-ghost);">-</span>'}</td>
                        <td>${missingTags || '<span style="color: var(--text-ghost);">-</span>'}</td>
                        <td>${newTags || '<span style="color: var(--text-ghost);">-</span>'}</td>
                        <td>${conflictTags || '<span style="color: var(--text-ghost);">-</span>'}</td>
                    </tr>`;
    });

    tableHtml += '</tbody></table></div></div>';

    // Missing signatures section
    let missingSigs = [];
    results.forEach(r => {
        (r.unique_signatures?.missing || []).forEach(s => {
            if (!missingSigs.find(m => m.sig === s && m.provider === r.provider)) {
                missingSigs.push({ provider: r.provider, sig: s });
            }
        });
    });

    let missingHtml = '';
    if (missingSigs.length > 0) {
        missingHtml = `
                <div class="sig-detail-section sig-report-container">
                    <div class="sig-section-title">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--neon-red)" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                        缺失签名
                        <span class="count-badge" style="background: var(--glow-red); color: var(--neon-red);">${missingSigs.length}</span>
                    </div>
                    <div class="sig-detail-content">
                        ${missingSigs.map(m => `<div class="sig-conflict-item"><span style="font-weight: 600; min-width: 120px;">${m.provider}</span><span class="sig-tag missing">${m.sig}</span></div>`).join('')}
                    </div>
                </div>`;
    }

    // Conflicts section
    let allConflicts = [];
    results.forEach(r => {
        (r.conflicts || []).forEach(c => {
            if (!allConflicts.find(x => x.signature === c.signature && x.provider === r.provider)) {
                allConflicts.push({ provider: r.provider, signature: c.signature, other: c.other_provider });
            }
        });
    });

    let conflictsHtml = '';
    if (allConflicts.length > 0) {
        conflictsHtml = `
                <div class="sig-detail-section sig-report-container">
                    <div class="sig-section-title">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--neon-amber)" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        签名冲突
                        <span class="count-badge" style="background: rgba(255, 187, 51, 0.1); color: var(--neon-amber);">${allConflicts.length}</span>
                    </div>
                    <div class="sig-detail-content">
                        ${allConflicts.map(c => `<div class="sig-conflict-item"><span style="font-weight: 600; min-width: 120px;">${c.provider}</span><span class="sig-tag conflict">${c.signature}</span><span style="color: var(--text-ghost);">与</span><span style="font-weight: 600;">${c.other}</span><span style="color: var(--text-ghost);">冲突</span></div>`).join('')}
                    </div>
                </div>`;
    }

    // Response body details
    let detailsHtml = `
            <div class="sig-detail-section sig-report-container">
                <div class="sig-section-title">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    测试响应详情
                    <span class="count-badge">${results.length}</span>
                </div>
                <div class="sig-detail-content">
                    ${results.map(r => {
                        const es = r.test_result || {};
                        const respBody = es.response_body || '(空)';
                        const sc = es.error === 'timeout' ? 'timeout' : (es.valid ? 'ok' : 'error');
                        return `<div class="sig-conflict-item" style="flex-direction: column; align-items: flex-start; gap: 6px;">
                            <div style="display: flex; align-items: center; gap: 10px; width: 100%;">
                                <span style="font-weight: 600; min-width: 120px;">${r.provider}</span>
                                <span class="sig-status-badge ${sc}">${es.valid ? '200 OK' : (es.status_code || es.error || 'N/A')}</span>
                                <span style="color: var(--text-ghost); font-family: 'Fira Code', monospace; font-size: 11px;">${es.latency_ms ? Math.round(es.latency_ms) + 'ms' : '-'}</span>
                            </div>
                            <div class="sig-response-body">${respBody.substring(0, 500)}</div>
                        </div>`;
                    }).join('')}
                </div>
            </div>`;

    body.innerHTML = summaryHtml + tableHtml + missingHtml + conflictsHtml + detailsHtml + '</div>';
}

// ─── Add Provider Modal ──────────────────────────────────────────────────────

export function showAddProviderModal() {
    document.getElementById('add-provider-modal').classList.add('show');
}

export function closeAddProviderModal() {
    document.getElementById('add-provider-modal').classList.remove('show');
    // Clear form
    document.getElementById('add-provider-name').value = '';
    document.getElementById('add-provider-display').value = '';
    document.getElementById('add-provider-url').value = '';
    document.getElementById('add-provider-endpoint').value = '';
    document.getElementById('add-provider-prefix').value = '';
}

export async function submitAddProvider() {
    const name = document.getElementById('add-provider-name').value.trim();
    const base_url = document.getElementById('add-provider-url').value.trim();
    const check_endpoint = document.getElementById('add-provider-endpoint').value.trim();
    const display_name = document.getElementById('add-provider-display').value.trim();
    const key_prefix = document.getElementById('add-provider-prefix').value.trim();

    if (!name || !base_url || !check_endpoint) {
        showToast('请填写必填字段', 'error');
        return;
    }

    const body = {
        name,
        base_url,
        check_endpoint,
        display_name: display_name || name,
        key_prefixes: key_prefix ? [key_prefix] : [],
    };

    try {
        const resp = await safeFetch('/api/providers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (resp.success) {
            showToast('服务商添加成功', 'success');
            closeAddProviderModal();
            // Refresh providers list
            if (typeof loadProviders === 'function') loadProviders();
        } else {
            showToast(resp.message || '添加失败', 'error');
        }
    } catch (e) {
        showToast('添加失败: ' + (e.message || '服务器错误'), 'error');
    }
}
