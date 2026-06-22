/**
 * Models API — /api/models
 */
import { getTypeLabel } from '../utils.js';
import { State } from '../state.js';
import { safeFetch } from './client.js';

let _toast;
async function _loadUI() {
  if (!_toast) _toast = await import('../toast.js');
}

// 检测状态管理
let currentCheckController = null;
let isChecking = false;

export async function getModels() {
  await _loadUI();
  const key = document.getElementById('manual-key').value.trim();
  const provider = document.getElementById('manual-provider').value;

  if (!key && !provider) { _toast.showToast('请输入 Key 或选择服务商', 'error'); return; }

  const typeFilter = document.getElementById('model-type-filter').value;
  const resultEl = document.getElementById('manual-result');
  resultEl.innerHTML = '<div class="result-card"><div style="color: var(--neon-cyan); display: flex; align-items: center; gap: 10px;"><div class="progress-spinner" style="width: 20px; height: 20px;"></div> 获取模型列表...</div></div>';

  try {
    const params = new URLSearchParams();
    if (provider) params.set('provider', provider);
    if (key) params.set('key', key);
    if (typeFilter && typeFilter !== 'all') params.set('type_filter', typeFilter);

    const data = await safeFetch(`/api/models?${params}`);

    if (data.error) {
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">${data.error}</div></div>`;
      return;
    }

    if (data.models.length === 0) {
      const typeLabel = typeFilter !== 'all' ? ` (${getTypeLabel(typeFilter)})` : '';
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-amber);">${data.provider}${typeLabel} 暂无模型</div></div>`;
      return;
    }

    const typeLabel = data.type_filter && data.type_filter !== 'all' ? ` - ${getTypeLabel(data.type_filter)}` : '';
    const sourceLabel = data.source === 'static' ? ' <span class="badge" style="background: var(--neon-amber-dim); color: var(--neon-amber); font-size: 10px;">静态</span>' : '';
    resultEl.innerHTML = `
      <div class="result-card">
        <div class="result-header">
          <span class="result-key">${data.provider}${typeLabel}${sourceLabel}</span>
          <span class="badge badge-valid">${data.models.length} 个模型</span>
        </div>
        <div class="models-tags" style="margin-top: 12px;">
          ${data.models.map(m => `<span class="model-chip">${m}</span>`).join('')}
        </div>
      </div>`;
  } catch (e) {
    resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">获取失败: ${e.message}</div></div>`;
  }
}

export async function checkAvailableModels() {
  await _loadUI();
  if (isChecking && currentCheckController) {
    currentCheckController.abort();
    currentCheckController = null;
    isChecking = false;
    _toast.showToast('已终止检测', 'info');
    return;
  }

  const key = document.getElementById('manual-key').value.trim();
  if (!key) { _toast.showToast('请先输入 Key', 'error'); return; }

  const provider = document.getElementById('manual-provider').value;
  const typeFilter = document.getElementById('model-type-filter').value;
  const resultEl = document.getElementById('manual-result');

  currentCheckController = new AbortController();
  isChecking = true;

  const typeLabel = typeFilter !== 'all' ? ` (${getTypeLabel(typeFilter)})` : '';
  resultEl.innerHTML = `
    <div class="result-card">
      <div style="display: flex; align-items: flex-start; gap: 10px;">
        <div class="progress-spinner" style="width: 20px; height: 20px; margin-top: 2px;"></div>
        <div style="flex: 1;">
          <div style="font-weight: 500;">检测可用模型${typeLabel}中...</div>
          <div style="color: var(--neon-amber); font-size: 11px; margin-top: 4px;">(再次点击按钮终止)</div>
          <div id="check-progress" style="font-size: 11px; color: var(--text-ghost); margin-top: 4px;">准备中</div>
        </div>
      </div>
      <div id="check-results" style="margin-top: 12px;"></div>
    </div>`;

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (State.apiToken) {
      headers['Authorization'] = `Bearer ${State.apiToken}`;
    }
    const response = await fetch('/api/models/check', {
      method: 'POST',
      headers,
      body: JSON.stringify({ key, provider: provider || '', type: typeFilter }),
      signal: currentCheckController.signal
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    const progressEl = document.getElementById('check-progress');
    const resultsEl = document.getElementById('check-results');
    const availableModels = [];
    const timeoutModels = [];
    const errorModels = [];
    let forceSerialMode = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'progress') {
              const modeLabel = forceSerialMode ? ' (串行)' : (data.mode === 'serial' ? ' (串行)' : ' (并行)');
              progressEl.textContent = `检测中: ${data.current}/${data.total} - ${data.model}${modeLabel}`;
            } else if (data.type === 'rate_limited') {
              forceSerialMode = true;
              progressEl.textContent = `被限流，切换到串行模式...`;
              progressEl.style.color = 'var(--neon-amber)';
            } else if (data.type === 'model_timeout') {
              if (!timeoutModels.includes(data.model)) {
                timeoutModels.push(data.model);
                progressEl.textContent = `模型 ${data.model} 超时，跳过...`;
                progressEl.style.color = 'var(--neon-amber)';
                if (!document.getElementById('timeout-models-tags')) {
                  resultsEl.innerHTML += '<div style="margin-top: 8px;"><span style="color: var(--neon-red); font-size: 11px;">超时模型:</span><div class="models-tags" id="timeout-models-tags" style="margin-top: 4px;"></div></div>';
                }
                const timeoutTagsEl = document.getElementById('timeout-models-tags');
                timeoutTagsEl.innerHTML += `<span class="model-chip" style="border-color: var(--neon-red); color: var(--neon-red); background: rgba(255, 68, 68, 0.1);">${data.model}</span> `;
              }
            } else if (data.type === 'result') {
              if (data.available) {
                if (!availableModels.includes(data.model)) {
                  availableModels.push(data.model);
                  const timeoutIdx = timeoutModels.indexOf(data.model);
                  if (timeoutIdx > -1) {
                    timeoutModels.splice(timeoutIdx, 1);
                    const timeoutTagsEl = document.getElementById('timeout-models-tags');
                    if (timeoutTagsEl) {
                      const chips = timeoutTagsEl.querySelectorAll('.model-chip');
                      chips.forEach(chip => { if (chip.textContent === data.model) chip.remove(); });
                    }
                  }
                  if (!document.getElementById('available-models-tags')) {
                    resultsEl.innerHTML = '<div><span style="color: var(--neon-green); font-size: 11px;">可用模型:</span><div class="models-tags" id="available-models-tags" style="margin-top: 4px;"></div></div>' + resultsEl.innerHTML;
                  }
                  const tagsEl = document.getElementById('available-models-tags');
                  tagsEl.innerHTML += `<span class="model-chip" style="border-color: var(--neon-green); color: var(--neon-green); background: rgba(0, 255, 136, 0.1);">${data.model}</span> `;
                }
              } else if (data.status === 'error') {
                if (!errorModels.includes(data.model)) {
                  errorModels.push(data.model);
                  if (!document.getElementById('error-models-tags')) {
                    resultsEl.innerHTML += '<div style="margin-top: 8px;"><span style="color: var(--neon-magenta); font-size: 11px;">检测失败:</span><div class="models-tags" id="error-models-tags" style="margin-top: 4px;"></div></div>';
                  }
                  const errorTagsEl = document.getElementById('error-models-tags');
                  errorTagsEl.innerHTML += `<span class="model-chip" style="border-color: var(--neon-magenta); color: var(--neon-magenta); background: rgba(255, 68, 187, 0.1);">${data.model}</span> `;
                }
              } else if (data.status === 'rate_limited') {
                if (!document.getElementById('rate-limited-models-tags')) {
                  resultsEl.innerHTML += '<div style="margin-top: 8px;"><span style="color: var(--neon-amber); font-size: 11px;">被限流:</span><div class="models-tags" id="rate-limited-models-tags" style="margin-top: 4px;"></div></div>';
                }
                const rateLimitedTagsEl = document.getElementById('rate-limited-models-tags');
                rateLimitedTagsEl.innerHTML += `<span class="model-chip" style="border-color: var(--neon-amber); color: var(--neon-amber); background: rgba(255, 187, 51, 0.1);">${data.model}</span> `;
              }
            } else if (data.type === 'complete') {
              const modeLabel = forceSerialMode ? ' (串行模式)' : (data.mode === 'serial' ? ' (串行模式)' : '');
              const timeoutLabel = data.timeout > 0 ? `, ${data.timeout} 超时` : '';

              const titleEl = resultEl.querySelector('div[style*="font-weight: 500"]');
              if (titleEl) titleEl.textContent = `可用模型 (${availableModels.length}/${data.total})`;

              progressEl.textContent = `检测完成${timeoutLabel}${modeLabel}`;
              progressEl.style.color = 'var(--neon-green)';

              const spinner = resultEl.querySelector('.progress-spinner');
              if (spinner) spinner.style.display = 'none';
              const abortHint = resultEl.querySelector('div[style*="neon-amber"]');
              if (abortHint && abortHint.textContent.includes('终止')) abortHint.style.display = 'none';

              isChecking = false;
              currentCheckController = null;
            }
          } catch (e) {}
        }
      }
    }

    if (availableModels.length === 0 && timeoutModels.length === 0) {
      resultsEl.innerHTML = '<div style="color: var(--neon-amber); margin-top: 8px;">未找到可用模型</div>';
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-amber);">检测已终止</div></div>`;
    } else {
      resultEl.innerHTML = `<div class="result-card"><div style="color: var(--neon-red);">检测失败: ${e.message}</div></div>`;
    }
  } finally {
    isChecking = false;
    currentCheckController = null;
  }
}
