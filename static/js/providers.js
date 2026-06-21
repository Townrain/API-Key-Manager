/**
 * Provider grid and detail modal module.
 * Extracted from templates/index.html ~lines 3170, 3590-3603, 4039-4110.
 */

import { State } from './state.js';
import { esc, escAttr } from './utils.js';
import { showToast } from './toast.js';

export function toggleProviders() {
    document.getElementById('providers-grid').classList.toggle('collapsed');
}

export function showProviderDetail(providerName) {
    const info = State.PROVIDER_WEBSITES_MAP[providerName];
    const body = document.getElementById('provider-detail-body');
    const title = document.getElementById('provider-detail-title');

    if (!info) {
        // Fallback: use DISPLAY_NAMES
        const dn = State.DISPLAY_NAMES[providerName] || providerName;
        title.textContent = dn;
        body.innerHTML = `
            <div class="provider-detail-hero">
                <div class="prov-name">${dn}</div>
                <div class="prov-internal">${providerName}</div>
            </div>
            <div class="provider-detail-info">
                <div class="info-row"><span class="info-label">内部名称</span><span class="info-value">${providerName}</span></div>
                <div class="info-row"><span class="info-label">显示名称</span><span class="info-value">${dn}</span></div>
            </div>`;
        document.getElementById('provider-detail-modal').classList.add('show');
        return;
    }

    title.textContent = info.website_name || info.display_name;

    const websiteHtml = info.website_url ? `
        <a class="provider-detail-link" href="${info.website_url}" target="_blank" rel="noopener">
            <div class="link-icon website">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            </div>
            <div class="link-text">
                <div class="link-label">官方网站</div>
                <div class="link-url">${info.website_url}</div>
            </div>
            <svg class="link-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17l9.2-9.2M17 17V7H7"/></svg>
        </a>` : '<div style="padding: 12px 18px; color: var(--text-ghost); font-size: 13px;">暂无官网链接</div>';

    const docsHtml = info.docs_url ? `
        <a class="provider-detail-link" href="${info.docs_url}" target="_blank" rel="noopener">
            <div class="link-icon docs">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            </div>
            <div class="link-text">
                <div class="link-label">API 文档</div>
                <div class="link-url">${info.docs_url}</div>
            </div>
            <svg class="link-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17l9.2-9.2M17 17V7H7"/></svg>
        </a>` : '<div style="padding: 12px 18px; color: var(--text-ghost); font-size: 13px;">暂无文档链接</div>';

    body.innerHTML = `
        <div class="provider-detail-hero">
            <div class="prov-name">${info.website_name || info.display_name}</div>
            <div class="prov-internal">${info.name}</div>
        </div>
        <div class="provider-detail-links">
            ${websiteHtml}
            ${docsHtml}
        </div>
        <div class="provider-detail-info">
            <div class="info-row"><span class="info-label">内部名称</span><span class="info-value">${info.name}</span></div>
            <div class="info-row"><span class="info-label">显示名称</span><span class="info-value">${info.display_name}</span></div>
            ${info.prefix && info.prefix !== '-' ? `<div class="info-row"><span class="info-label">Key 前缀</span><span class="info-value" style="color: var(--neon-cyan);">${info.prefix}</span></div>` : ''}
            ${info.base_url ? `<div class="info-row"><span class="info-label">Base URL</span><span class="info-value" style="word-break: break-all; font-size: 11px;">${info.base_url}</span></div>` : ''}
        </div>`;

    document.getElementById('provider-detail-modal').classList.add('show');
}

export function closeProviderDetailModal() {
    document.getElementById('provider-detail-modal').classList.remove('show');
}

export function populateProviderDropdown(providers) {
    const dropdown = document.getElementById('provider-dropdown');
    if (!dropdown) return;

    // Keep the first "auto detect" option
    let html = '<div class="custom-select-option selected" data-value="" onclick="selectCustomOption(\'provider-select\', \'\', \'自动识别\')">自动识别</div>';

    providers.forEach(p => {
        html += `<div class="custom-select-option" data-value="${p}" onclick="selectCustomOption('provider-select', '${p}', '${p}')">${p}</div>`;
    });

    dropdown.innerHTML = html;
}
