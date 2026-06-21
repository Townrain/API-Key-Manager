/**
 * Test API — /api/test
 */
import { safeFetch } from './client.js';

let _toast, _progress;
async function _loadUI() {
  if (!_toast) {
    _toast = await import('../toast.js');
    _progress = await import('../progress.js');
  }
}

export async function runTokenTest() {
  await _loadUI();
  const key = document.getElementById('manual-key').value.trim();
  if (!key) { _toast.showToast('请先输入 Key', 'error'); return; }
  const provider = document.getElementById('manual-provider').value;
  const resultEl = document.getElementById('manual-result');
  resultEl.innerHTML = '<div class="result-card"><div style="color: var(--neon-cyan); display: flex; align-items: center; gap: 10px;"><div class="progress-spinner" style="width: 20px; height: 20px;"></div> 正在测试Token上限...</div></div>';
  try {
    const data = await safeFetch('/api/test/token', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key, provider: provider || ''})
    });
    if (data.error) {
      resultEl.innerHTML = '<div class="result-card"><div style="color: var(--neon-red);">' + data.error + '</div></div>';
      return;
    }
    let modelResultsHtml = '';
    let allMaxTokens = [];
    if (data.results && data.results.length > 0) {
      data.results.forEach(r => {
        if (r.max_tokens) {
          allMaxTokens.push(r.max_tokens);
        }
      });
      modelResultsHtml = '<div style="margin-top: 12px;"><label style="font-family: Fira Code, monospace; font-size: 12px; color: var(--text-ghost); text-transform: uppercase; letter-spacing: 1px;">各模型Token上限</label><div style="margin-top: 8px; display: grid; gap: 8px;">' +
        data.results.map(r => {
          const statusHtml = r.success
            ? '<span style="color: var(--neon-green); font-weight: 600;">' + r.max_tokens.toLocaleString() + ' tokens</span>'
            : (r.max_tokens
              ? '<span style="color: var(--neon-cyan); font-weight: 600;">' + r.max_tokens.toLocaleString() + ' tokens</span>'
              : '<span style="color: var(--neon-red);">检测失败</span>');
          return '<div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--surface-2); border-radius: 8px;"><span class="model-chip">' + r.model + '</span><div style="text-align: right;">' + statusHtml + '</div></div>';
        }).join('') + '</div></div>';
    }
    let summaryHtml = '';
    if (allMaxTokens.length > 0) {
      const minMax = Math.min(...allMaxTokens);
      summaryHtml = '<div style="margin-top: 12px; padding: 10px 14px; background: rgba(0, 232, 255, 0.1); border: 1px solid rgba(0, 232, 255, 0.3); border-radius: 8px;"><div style="display: flex; align-items: center; gap: 8px; color: var(--neon-cyan); font-size: 12px;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg><span>此Key的最大输出Token上限: <strong>' + minMax.toLocaleString() + '</strong></span></div></div>';
    }
    resultEl.innerHTML = '<div class="result-card"><div class="result-header"><span class="result-key">' + data.key_masked + '</span><span class="badge badge-valid">测试完成</span></div><div class="result-grid"><div class="result-item"><label>服务商</label><value>' + data.provider + '</value></div><div class="result-item"><label>可用模型</label><value>' + data.total_models + '</value></div><div class="result-item"><label>已测试</label><value>' + data.tested_models + '</value></div></div>' + modelResultsHtml + summaryHtml + '</div>';
    _toast.showToast('Token上限测试完成', 'success');
  } catch (e) {
    resultEl.innerHTML = '<div class="result-card"><div style="color: var(--neon-red);">测试失败: ' + e.message + '</div></div>';
  }
}

export async function runConcurrencyTest() {
  await _loadUI();
  const key = document.getElementById('manual-key').value.trim();
  if (!key) { _toast.showToast('请先输入 Key', 'error'); return; }

  const concurrencyInput = document.getElementById('concurrency-input');
  const concurrency = parseInt(concurrencyInput.value);
  if (!concurrency || concurrency < 1) {
    _toast.showToast('请填写并发数（至少为 1）', 'error');
    concurrencyInput.focus();
    return;
  }
  if (concurrency > 10000) {
    _toast.showToast('并发数不能超过 10000', 'error');
    concurrencyInput.focus();
    return;
  }

  const provider = document.getElementById('manual-provider').value;
  const resultEl = document.getElementById('manual-result');
  resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-cyan); display: flex; align-items: center; gap: 10px;"><div class="progress-spinner" style="width: 20px; height: 20px;"></div> 并发测试中（并发数: ${concurrency}）...</div></div>`;
  try {
    const data = await safeFetch('/api/test/concurrency', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({key, provider: provider || '', concurrency: concurrency})
    });

    if (data.error) {
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">${data.error}</div></div>`;
      return;
    }

    let modelResultsHtml = '';
    if (data.results && data.results.length > 0) {
      modelResultsHtml = `
        <div style="margin-top: 12px;">
          <label style="font-family: 'Fira Code', monospace; font-size: 12px; color: var(--text-ghost); text-transform: uppercase; letter-spacing: 1px;">模型并发测试结果</label>
          <div style="margin-top: 8px; display: grid; gap: 8px;">
            ${data.results.map(r => `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--surface-2); border-radius: 8px;">
                <span class="model-chip">${r.model}</span>
                <span style="color: ${r.max_concurrency ? 'var(--neon-green)' : 'var(--neon-red)'}; font-weight: 600;">
                  ${r.max_concurrency ? r.max_concurrency + ' 并发' : '失败'}
                </span>
              </div>
            `).join('')}
          </div>
        </div>`;
    }

    resultEl.innerHTML = `
      <div class="result-card">
        <div class="result-header">
          <span class="result-key">${data.key_masked}</span>
          <span class="badge badge-valid">测试完成</span>
        </div>
        <div class="result-grid">
          <div class="result-item"><label>服务商</label><value>${data.provider}</value></div>
          <div class="result-item"><label>可用模型</label><value>${data.total_models}</value></div>
          <div class="result-item"><label>已测试</label><value>${data.tested_models}</value></div>
        </div>
        ${modelResultsHtml}
      </div>`;
    _toast.showToast('并发测试完成', 'success');
  } catch (e) {
    resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">测试失败: ${e.message}</div></div>`;
  }
}

export async function runTokenTestBatch() {
  await _loadUI();
  const provider = document.getElementById('provider-filter').value;
  _progress.showProgress('Token检测中', '正在逐模型测试Token上限...', 'token');
  const pi = setInterval(async () => { try { const d = await safeFetch('/api/progress'); if (d.active) _progress.updateProgress(d.current, d.total); } catch (e) {} }, 200);
  try {
    const data = await safeFetch('/api/test/token/batch', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({provider: provider || null}) });
    clearInterval(pi); _progress.hideProgress();
    _toast.showToast(`Token检测完成: ${data.total_tested} 个Key`, 'success');
    const { loadStats } = await import('./stats.js'); const { loadKeys } = await import('./keys.js'); loadStats(); loadKeys();
  } catch (e) { clearInterval(pi); _progress.hideProgress(); _toast.showToast('Token检测失败: ' + e.message, 'error'); }
}

export async function runConcurrencyTestBatch() {
  await _loadUI();
  const provider = document.getElementById('provider-filter').value;
  _progress.showProgress('并发测试中', '正在逐模型测试并发能力...');
  const pi = setInterval(async () => { try { const d = await safeFetch('/api/progress'); if (d.active) _progress.updateProgress(d.current, d.total); } catch (e) {} }, 200);
  try {
    const data = await safeFetch('/api/test/concurrency/batch', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({provider: provider || null, concurrency: 10}) });
    clearInterval(pi); _progress.hideProgress();
    _toast.showToast(`并发测试完成: ${data.total_tested} 个Key`, 'success');
    const { loadStats } = await import('./stats.js'); const { loadKeys } = await import('./keys.js'); loadStats(); loadKeys();
  } catch (e) { clearInterval(pi); _progress.hideProgress(); _toast.showToast('并发测试失败: ' + e.message, 'error'); }
}
