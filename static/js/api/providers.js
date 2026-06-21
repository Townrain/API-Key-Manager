/**
 * Providers API — /api/providers
 */
import { State } from '../state.js';
import { esc, escAttr } from '../utils.js';
import { safeFetch } from './client.js';

export async function loadProviders() {
  try {
    const data = await safeFetch('/api/providers');
    const grid = document.getElementById('providers-grid');
    document.getElementById('providers-card-title').textContent = `支持的服务商 (${data.total})`;

    try {
      const detailData = await safeFetch('/api/providers/detail');
      if (detailData.providers) {
        detailData.providers.forEach(p => { State.PROVIDER_WEBSITES_MAP[p.name] = p; });
      }
    } catch (e) { console.error('Failed to load provider details:', e); }

    const withPrefix = data.providers.filter(p => p.prefix !== '-');
    const withoutPrefix = data.providers.filter(p => p.prefix === '-');

    const renderChips = (list) => list.map(p =>
      `<span class="provider-chip-item ai" title="${escAttr(p.base_url || '')}" data-provider="${escAttr(p.name)}" onclick="showProviderDetail('${escAttr(p.name)}')" style="cursor: pointer;">${esc(p.display_name || p.name)}${p.prefix !== '-' ? ' <b>' + esc(p.prefix) + '</b>' : ''}</span>`
    ).join('');

    grid.innerHTML = `
      <div class="provider-cat">
        <div class="provider-cat-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/></svg>
          唯一前缀 (${withPrefix.length})
        </div>
        <div class="provider-chips">${renderChips(withPrefix)}</div>
      </div>
      <div class="provider-cat">
        <div class="provider-cat-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg>
          共享前缀 / 无固定前缀 (${withoutPrefix.length})
        </div>
        <div class="provider-chips">${renderChips(withoutPrefix)}</div>
      </div>
    `;

    const dropdown = document.getElementById('provider-dropdown');
    const hiddenInput = document.getElementById('manual-provider');
    const currentVal = hiddenInput ? hiddenInput.value : '';

    let dropdownHtml = '<div class="custom-select-option' + (currentVal === '' ? ' selected' : '') + '" data-value="" onclick="selectCustomOption(\'provider-select\', \'\', \'自动识别\')">自动识别</div>';
    data.providers.forEach(p => {
      const selected = p.name === currentVal ? ' selected' : '';
      dropdownHtml += `<div class="custom-select-option${selected}" data-value="${p.name}" onclick="selectCustomOption('provider-select', '${p.name}', '${esc(p.display_name || p.name)}')">${esc(p.display_name || p.name)}</div>`;
      State.PROVIDERS_MAP[p.name] = p;
      State.DISPLAY_NAMES[p.name] = p.display_name || p.name;
    });
    if (dropdown) dropdown.innerHTML = dropdownHtml;
    if (hiddenInput) hiddenInput.value = currentVal;

    const labelEl = document.getElementById('provider-label');
    if (labelEl && currentVal) {
      labelEl.textContent = State.DISPLAY_NAMES[currentVal] || currentVal;
    }
  } catch (e) {
    console.error('Failed to load providers:', e);
  }
}
