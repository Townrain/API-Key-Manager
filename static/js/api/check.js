/**
 * Check API — /api/check
 */
import { State } from '../state.js';
import { translateError, translateErrorType } from '../utils.js';
import { safeFetch } from './client.js';

let _toast, _progress;
async function _loadUI() {
  if (!_toast) {
    _toast = await import('../toast.js');
    _progress = await import('../progress.js');
  }
}

export async function checkManualKey() {
  await _loadUI();
  const keyInput = document.getElementById('manual-key');
  const providerSel = document.getElementById('manual-provider');
  const resultEl = document.getElementById('manual-result');
  const key = keyInput.value.trim();
  if (!key) { _toast.showToast('请输入 Key', 'error'); return; }
  const customUrl = document.getElementById('custom-base-url').value.trim();

  resultEl.innerHTML = '<div class="result-card"><div style="color: var(--neon-cyan); display: flex; align-items: center; gap: 10px;"><div class="progress-spinner" style="width: 20px; height: 20px;"></div> 检测中...</div></div>';

  try {
    const body = {key, provider: providerSel.value, custom_base_url: customUrl || null};
    const data = await safeFetch('/api/check/single', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
    if (data.error && !data.status) {
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">${data.error}</div></div>`;
    } else {
      const sc = data.status === 'valid' ? 'valid' : (data.status === 'invalid' ? 'invalid' : 'error');
      const tt = 'API 检测';
      const mh = data.models && data.models.length > 0
        ? `<div style="margin-top: 12px;"><label style="font-family: 'Fira Code', monospace; font-size: 12px; color: var(--text-ghost); text-transform: uppercase; letter-spacing: 1px;">模型 (${data.models.length})</label><div class="models-tags" style="margin-top: 6px;">${data.models.slice(0, 5).map(m => `<span class="model-chip">${m.length > 15 ? m.substring(0, 12) + '...' : m}</span>`).join('')}${data.models.length > 5 ? `<span class="model-chip more">+${data.models.length - 5}</span>` : ''}</div></div>` : '';

      const te = translateError(data.error || '');
      const tet = translateErrorType(data.error_type || '');
      const balanceHtml = data.balance ? `<div class="result-item"><label>余额</label><value style="color: var(--neon-green);">${data.balance.balance} ${data.balance.currency}</value></div>` : '';
      const errorTypeHtml = data.error_type ? `<div style="margin-top: 8px; padding: 8px 12px; background: var(--glow-red); border-radius: 8px; font-size: 13px;"><span style="color: var(--neon-amber);">⚠ ${tet || data.error_type}</span></div>` : '';
      resultEl.innerHTML = `
        <div class="result-card">
          <div class="result-header"><span class="result-key">${data.key_masked}</span><span class="badge badge-${sc}">${State.STATUS_MAP[data.status] || data.status}</span></div>
          <div class="result-grid">
            <div class="result-item"><label>检测方式</label><value>${tt}</value></div>
            <div class="result-item"><label>服务商</label><value>${data.display_name || data.provider}</value></div>
            <div class="result-item"><label>状态码</label><value>${data.status_code || '-'}</value></div>
            <div class="result-item"><label>延迟</label><value>${data.latency_ms > 0 ? Math.round(data.latency_ms) + 'ms' : (data.status_code === 200 && !data.latency_ms ? '自动识别' : '-')}</value></div>
            ${balanceHtml}
          </div>
          ${errorTypeHtml}
          ${data.error ? `<div class="result-error"><div class="label">错误信息</div><div>${te ? te : ''}</div><div class="msg">${data.error}</div></div>` : ''}
          ${mh}
        </div>`;

      if (data.status === 'valid') { _toast.showToast(`Key 可用 (${tt})`, 'success'); const { loadStats } = await import('./stats.js'); const { loadKeys } = await import('./keys.js'); loadStats(); loadKeys(); }
    }
  } catch (e) {
    resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">检测失败: ${e.message}</div></div>`;
  }
}

export async function runCheck() {
  await _loadUI();
  const provider = document.getElementById('provider-filter').value;
  _progress.showProgress('检测中', '正在调用 API 验证...');
  const pi = setInterval(async () => { try { const d = await safeFetch('/api/progress'); if (d.active) _progress.updateProgress(d.current, d.total); } catch (e) {} }, 200);
  try {
    const data = await safeFetch('/api/check', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({provider: provider || null}) });
    clearInterval(pi); _progress.hideProgress();
    if (data.summary) {
      _toast.showToast(`检测完成: ${data.summary.valid.count} 有效, ${data.summary.invalid.count} 无效`, 'success');
      document.querySelectorAll('.stat-card').forEach((c, i) => { setTimeout(() => { c.style.animation = 'flash 0.6s ease'; setTimeout(() => c.style.animation = '', 600); }, i * 100); });
    }
    const { loadStats } = await import('./stats.js'); const { loadKeys } = await import('./keys.js'); loadStats(); loadKeys();
  } catch (e) { clearInterval(pi); _progress.hideProgress(); _toast.showToast('检测失败: ' + e.message, 'error'); }
}

export async function runBatchCheck() {
  await _loadUI();
  const textarea = document.getElementById('batch-keys-input');
  const resultsEl = document.getElementById('batch-results');
  const hintEl = document.getElementById('batch-count-hint');
  const raw = textarea.value.trim();
  if (!raw) { _toast.showToast('请输入要检测的 Key', 'error'); return; }
  const keys = raw.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  if (keys.length === 0) { _toast.showToast('未找到有效的 Key', 'error'); return; }
  hintEl.textContent = `检测中 (${keys.length} 个)...`;
  resultsEl.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--neon-cyan);"><div class="progress-spinner" style="width: 24px; height: 24px; margin: 0 auto 8px;"></div>正在检测 ' + keys.length + ' 个 Key...</div>';

  try {
    const customUrl = document.getElementById('batch-custom-url')?.value.trim();
    const data = await safeFetch('/api/check/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys: keys, custom_base_url: customUrl || null })
    });
    const { showBatchResults } = await import('../batch.js');
    showBatchResults(data, hintEl);
  } catch (e) {
    resultsEl.innerHTML = `<div style="padding: 16px; color: var(--neon-red);">检测失败: ${e.message}</div>`;
    hintEl.textContent = '';
  }
}
