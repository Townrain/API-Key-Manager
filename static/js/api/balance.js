/**
 * Balance API — /api/balance
 */
import { safeFetch } from './client.js';

let _toast;
async function _loadUI() {
  if (!_toast) _toast = await import('../toast.js');
}

export async function checkBalance() {
  await _loadUI();
  const key = document.getElementById('manual-key').value.trim();
  if (!key) { _toast.showToast('请先输入 Key', 'error'); return; }
  const provider = document.getElementById('manual-provider').value;
  const customUrl = document.getElementById('custom-base-url').value.trim();
  const resultEl = document.getElementById('manual-result');
  resultEl.innerHTML = '<div class="result-card"><div style="color: var(--neon-cyan); display: flex; align-items: center; gap: 10px;"><div class="progress-spinner" style="width: 20px; height: 20px;"></div> 查询余额中...</div></div>';
  try {
    const data = await safeFetch('/api/balance', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key, provider: provider || '', custom_base_url: customUrl || null}) });
    if (data.error && !data.supported) {
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-amber);">${data.error}</div></div>`;
    } else if (data.error) {
      resultEl.innerHTML = `<div class="result-card">
        <div class="result-header"><span class="result-key">${data.key_masked || key.substring(0,6) + '...' + key.substring(key.length-4)}</span><span class="badge badge-error">查询失败</span></div>
        <div class="result-error"><div class="label">错误信息</div><div class="msg">${data.error}</div></div>
      </div>`;
    } else {
      resultEl.innerHTML = `<div class="result-card">
        <div class="result-header"><span class="result-key">${data.key_masked}</span><span class="badge badge-valid">查询成功</span></div>
        <div class="result-grid">
          <div class="result-item"><label>服务商</label><value>${data.provider}</value></div>
          <div class="result-item"><label>余额</label><value style="color: var(--neon-green); font-weight: 600;">${data.balance} ${data.currency}</value></div>
        </div>
      </div>`;
      _toast.showToast(`余额: ${data.balance} ${data.currency}`, 'success');
    }
  } catch (e) {
    resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">查询失败: ${e.message}</div></div>`;
  }
}
