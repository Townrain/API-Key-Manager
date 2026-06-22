/**
 * Misc API — /api/proxy, /api/logs
 */
import { safeFetch } from './client.js';

export async function loadProxy() {
  try {
    const data = await safeFetch('/api/proxy');
    const el = document.getElementById('proxy-status');
    if (data.proxy) {
      el.innerHTML = `<div class="status-dot"></div><span>${data.proxy}</span>`;
    } else {
      el.innerHTML = `<div class="status-dot offline"></div><span>无代理</span>`;
    }
  } catch (e) {
    const el = document.getElementById('proxy-status');
    el.innerHTML = `<div class="status-dot offline"></div><span>检测失败</span>`;
  }
}

export async function loadLogs() {
  const content = document.getElementById('logs-content');
  content.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--text-dim);">加载中...</div>';
  try {
    const data = await safeFetch('/api/logs?lines=200');
    if (data.logs.length === 0) { content.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-ghost);">暂无日志</div>'; return; }
    content.innerHTML = data.logs.reverse().map(line => {
      try {
        const regex = new RegExp('\\[(.*?)\\]\\s*\\[(.*?)\\]\\s*\\[(.*?)\\]\\s*(.*?)\\s*->\\s*(.*?)(?:\\s*\\((.*?)\\))?$');
        const m = line.match(regex);
        if (m && m.length >= 6) {
          const [_, ts, act, prov, key, st, detail] = m;
          const ac = act.trim().toLowerCase();
          const sc = st.trim().toLowerCase() === 'valid' ? 'valid' : st.trim().toLowerCase() === 'invalid' ? 'invalid' : st.trim().toLowerCase() === 'ok' ? 'valid' : 'error';
          return `<div class="log-entry"><span class="log-ts">${ts}</span> <span class="log-act ${ac}">${act.trim()}</span> <span class="log-prov">[${prov.trim()}]</span> <span class="log-key">${key.trim()}</span> -> <span class="log-st ${sc}">${st.trim()}</span> ${detail ? `<span style="color: var(--text-ghost);">(${detail})</span>` : ''}</div>`;
        }
      } catch (e) {}
      return `<div class="log-entry">${line}</div>`;
    }).join('');
  } catch (e) {
    content.innerHTML = `<div style="color: var(--neon-red); padding: 20px;">加载失败: ${e.message}</div>`;
  }
}

export async function clearLogs(date) {
  let _toast, _confirm;
  try { _toast = await import('../toast.js'); _confirm = await import('../confirm.js'); } catch {}
  const url = date ? `/api/logs?date=${date}` : '/api/logs';
  _confirm.showConfirm({
    title: '清除日志',
    message: date ? `确定要清除 ${date} 的日志吗？此操作不可恢复。` : '确定要清除今天的日志吗？此操作不可恢复。',
    icon: 'danger',
    okText: '清除',
    onConfirm: async () => {
      try {
        const data = await safeFetch(url, { method: 'DELETE' });
        if (data.success) {
          _toast.showToast(`已清除 ${data.date} 的日志 (${data.deleted_lines} 行)`, 'success');
          loadLogs();
        } else {
          _toast.showToast(data.error || '清除失败', 'error');
        }
      } catch (e) {
        _toast.showToast(`清除失败: ${e.message}`, 'error');
      }
    }
  });
}
