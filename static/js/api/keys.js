/**
 * Keys API — /api/keys, /api/import
 */
import { State } from '../state.js';
import { esc } from '../utils.js';
import { safeFetch } from './client.js';

// Lazy UI imports to avoid circular deps
let _toast, _keysTable;
async function _loadUI() {
  if (!_toast) {
    _toast = await import('../toast.js');
    _keysTable = await import('../keys-table.js');
  }
}

export async function loadKeys(page = State.currentPage) {
  const provider = document.getElementById('provider-filter').value;
  let params = new URLSearchParams({page, page_size: State.pageSize});
  if (provider) params.set('provider', provider);
  if (State.currentTab !== 'all') params.set('status', State.currentTab);
  if (State.showFullKeys) params.set('include_full_keys', 'true');
  const tbody = document.getElementById('keys-table');
  tbody.innerHTML = Array(5).fill('').map(() => `<tr class="skel-row"><td><div class="skeleton skel-bar" style="width: 180px;"></div></td><td><div class="skeleton skel-chip"></div></td><td><div class="skeleton skel-chip"></div></td><td><div class="skeleton skel-bar" style="width: 100px;"></div></td><td><div class="skeleton skel-bar" style="width: 80px;"></div></td><td><div class="skeleton skel-bar" style="width: 50px;"></div></td><td><div class="skeleton skel-chip" style="width: 30px;"></div></td><td><div class="skeleton skel-bar" style="width: 60px;"></div></td></tr>`).join('');
  try {
    await _loadUI();
    const data = await safeFetch(`/api/keys?${params}`);
    State.allKeys = data.keys;
    State.totalCount = data.total;
    State.currentPage = data.page;
    State.totalPages = data.total_pages;
    _keysTable.renderKeys();
  } catch (e) {
    console.error('[KeyHub] loadKeys failed:', e);
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state" style="color: var(--neon-red);"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg><h3>加载失败</h3><p>${esc(e.message)}</p></div></td></tr>`;
  }
}

export async function exportValidKeys() {
  await _loadUI();
  const data = await safeFetch('/api/keys/export');
  if (data.keys.length === 0) { _toast.showToast('没有有效的 Key', 'error'); return; }
  document.getElementById('export-text').value = data.keys.map(k => k.key_masked).join('\n');
  document.getElementById('export-modal').classList.add('show');
}

export async function clearAllKeys() {
  await _loadUI();
  const { showConfirm } = await import('../confirm.js');
  showConfirm({
    title: '清除所有密钥',
    message: '此操作将删除所有已导入的 API Key，操作不可撤销。',
    icon: 'danger',
    okText: '确认清除',
    onConfirm: async () => {
      try {
        const data = await safeFetch('/api/keys/clear', { method: 'POST' });
        _toast.showToast(`已清除 ${data.cleared} 个 Key`, 'success');
        const { loadStats } = await import('./stats.js');
        loadStats(); loadKeys();
      } catch (e) {
        _toast.showToast('清除失败: ' + e.message, 'error');
      }
    }
  });
}

export async function uploadFile(file) {
  await _loadUI();
  const status = document.getElementById('upload-status');
  status.className = 'upload-status loading';
  status.textContent = '正在上传...';
  const fd = new FormData();
  fd.append('file', file);
  try {
    const data = await safeFetch('/api/import/upload', { method: 'POST', body: fd });
    if (data.error) {
      status.className = 'upload-status error';
      status.textContent = data.error || '上传失败';
      _toast.showToast(data.error || '上传失败', 'error');
    } else {
      status.className = 'upload-status success';
      status.textContent = `完成: ${data.new} 新, ${data.duplicates} 重复`;
      _toast.showToast(`导入成功: ${data.new} 个新Key`, 'success');
      const { loadStats } = await import('./stats.js');
      loadStats(); loadKeys();
    }
  } catch (e) {
    status.className = 'upload-status error';
    status.textContent = e.message;
    _toast.showToast(e.message, 'error');
  }
  document.getElementById('file-input').value = '';
}

export async function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;
  uploadFile(file);
}
