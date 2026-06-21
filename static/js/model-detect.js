/**
 * Model detection modal module.
 * Extracted from templates/index.html ~lines 4321-4725.
 */

import { State } from './state.js';
import { esc, escAttr, getTypeLabel } from './utils.js';
import { safeFetch } from './api/client.js';
import { showToast } from './toast.js';

// Module-level state
let modalModels = [];  // All models in modal
let selectedModels = new Set();  // Selected model IDs
let modalModelsData = {};  // Model capabilities data
let modalModelsCache = {};  // Cache: { provider+key: { models: [...], caps: {...} } }

export function openModelDetectModal() {
    document.getElementById('model-detect-modal').classList.add('show');
    // Reset state
    modalModels = [];
    selectedModels = new Set();
    modalModelsData = {};
    renderModelList([]);
}

export function closeModelDetectModal() {
    document.getElementById('model-detect-modal').classList.remove('show');
    // Clear cache when modal is closed
    modalModelsCache = {};
}

export async function fetchModelsForModal() {
    const key = document.getElementById('manual-key').value.trim();
    const provider = document.getElementById('manual-provider').value;

    if (!key && !provider) {
        showToast('请先输入 Key 或选择服务商', 'error');
        return;
    }

    const listEl = document.getElementById('model-detect-list');
    const typeFilter = document.getElementById('modal-type-filter').value;
    const cacheKey = `${provider || 'all'}:${key || ''}`;

    // Check cache first - use cache if available
    if (modalModelsCache[cacheKey]) {
        const cached = modalModelsCache[cacheKey];
        const filtered = filterModelsByType(cached.models, typeFilter);
        modalModels = filtered;
        modalModelsData = cached.caps;
        selectedModels = new Set(filtered);
        renderModelList(filtered);
        updateSelectAllButton();
        showToast(`已从缓存筛选 ${filtered.length} 个模型`, 'success');
        return;
    }

    listEl.innerHTML = '<div style="color: var(--neon-cyan); text-align: center; padding: 40px;"><div class="progress-spinner" style="width: 20px; height: 20px; margin: 0 auto 10px;"></div>获取模型中...</div>';

    try {
        const params = new URLSearchParams();
        if (provider) params.set('provider', provider);
        if (key) params.set('key', key);
        // Always fetch all models first for caching
        params.set('type_filter', 'all');

        const data = await safeFetch(`/api/models?${params}`);

        if (data.error) {
            listEl.innerHTML = `<div style="color: var(--neon-red); text-align: center; padding: 40px;">${data.error}</div>`;
            return;
        }

        if (!data.models || data.models.length === 0) {
            listEl.innerHTML = '<div style="color: var(--neon-amber); text-align: center; padding: 40px;">未找到模型</div>';
            return;
        }

        // Fetch capabilities
        let caps = {};
        try {
            const capsParams = new URLSearchParams({ models: data.models.join(',') });
            const capsData = await safeFetch(`/api/models/capabilities?${capsParams}`);
            caps = capsData.capabilities || {};
        } catch (e) {
            console.warn('Failed to fetch capabilities:', e);
        }

        // Cache all models + capabilities
        modalModelsCache[cacheKey] = { models: data.models, caps: caps };

        // Apply type filter if needed
        let finalModels = data.models;
        if (typeFilter && typeFilter !== 'all') {
            finalModels = filterModelsByType(data.models, typeFilter);
        }

        modalModels = finalModels;
        modalModelsData = caps;
        selectedModels = new Set(finalModels);
        renderModelList(finalModels);
        updateSelectAllButton();

        showToast(`已获取 ${data.models.length} 个模型`, 'success');
    } catch (e) {
        listEl.innerHTML = `<div style="color: var(--neon-red); text-align: center; padding: 40px;">获取失败: ${e.message}</div>`;
    }
}

// Client-side model type filtering using cached capabilities
export function filterModelsByType(models, typeFilter) {
    if (!typeFilter || typeFilter === 'all') return models;
    return models.filter(m => {
        const caps = modalModelsData[m];
        switch (typeFilter) {
            case 'vision': return caps && caps.vision;
            case 'reasoning': return caps && caps.reasoning;
            case 'websearch': return caps && caps.websearch;
            case 'tooluse': return caps && caps.tooluse;
            case 'embedding': return caps && caps.embedding;
            case 'rerank': return caps && caps.rerank;
            case 'free': return (caps && caps.free) || /free/i.test(m);
            default: return true;
        }
    });
}

export function renderModelList(models) {
    const listEl = document.getElementById('model-detect-list');

    if (!models || models.length === 0) {
        listEl.innerHTML = '<div style="color: var(--text-ghost); text-align: center; padding: 40px;">请先点击"获取模型"按钮</div>';
        return;
    }

    const searchTerm = document.getElementById('model-search-input').value.toLowerCase();
    const filtered = searchTerm ? models.filter(m => m.toLowerCase().includes(searchTerm)) : models;

    if (filtered.length === 0) {
        listEl.innerHTML = '<div style="color: var(--text-ghost); text-align: center; padding: 40px;">未找到匹配的模型</div>';
        return;
    }

    // Type icon/text mapping
    const typeConfig = {
        vision: { icon: '👁️', color: '#00b96b', label: 'Vision' },
        reasoning: { icon: '💡', color: '#6372bd', label: 'Reasoning' },
        websearch: { icon: '🌐', color: '#1677ff', label: 'Web Search' },
        tooluse: { icon: '🔧', color: '#f18737', label: 'Tools' },
        embedding: { text: '嵌入', color: '#FFA500', label: 'Embedding' },
        rerank: { text: '重排', color: '#6495ED', label: 'Reranker' },
        free: { text: '免费', color: '#7cb305', label: 'Free' },
    };

    let html = '';
    for (const model of filtered) {
        const isSelected = selectedModels.has(model);
        const caps = modalModelsData[model] || {};

        // Build type icons/html
        let typeHtml = '';
        for (const [key, config] of Object.entries(typeConfig)) {
            if (caps[key]) {
                if (config.icon) {
                    typeHtml += `<span class="model-type-icon" style="color: ${config.color};" title="${config.label}">${config.icon}</span>`;
                } else if (config.text) {
                    typeHtml += `<span class="model-type-text" style="background: ${config.color}22; color: ${config.color};" title="${config.label}">${config.text}</span>`;
                }
            }
        }
        if (!typeHtml) {
            typeHtml = '<span style="color: var(--text-ghost); font-size: 11px;">-</span>';
        }

        html += `
                    <div class="model-detect-item" data-model="${model}">
                        <span class="model-detect-name" title="${model}">${model}</span>
                        <div class="model-detect-type">${typeHtml}</div>
                        <div class="model-detect-check ${isSelected ? 'selected' : ''}" onclick="toggleModelSelection('${model.replace(/'/g, "\\'")}')"></div>
                    </div>`;
    }

    listEl.innerHTML = html;
    updateSelectAllButton();
}

export function toggleModelSelection(model) {
    if (selectedModels.has(model)) {
        selectedModels.delete(model);
    } else {
        selectedModels.add(model);
    }

    // Update UI
    const item = document.querySelector(`.model-detect-item[data-model="${model}"] .model-detect-check`);
    if (item) {
        item.classList.toggle('selected', selectedModels.has(model));
    }
    updateSelectAllButton();
}

export function selectAllModels() {
    const searchTerm = document.getElementById('model-search-input').value.toLowerCase();
    const filtered = searchTerm ? modalModels.filter(m => m.toLowerCase().includes(searchTerm)) : modalModels;

    // Check if all filtered models are selected
    const allSelected = filtered.every(m => selectedModels.has(m));

    if (allSelected) {
        // Deselect all filtered
        for (const m of filtered) {
            selectedModels.delete(m);
        }
    } else {
        // Select all filtered
        for (const m of filtered) {
            selectedModels.add(m);
        }
    }

    renderModelList(modalModels);
}

export function updateSelectAllButton() {
    const btn = document.getElementById('select-all-btn');
    const searchTerm = document.getElementById('model-search-input').value.toLowerCase();
    const filtered = searchTerm ? modalModels.filter(m => m.toLowerCase().includes(searchTerm)) : modalModels;
    const allSelected = filtered.length > 0 && filtered.every(m => selectedModels.has(m));
    btn.textContent = allSelected ? '取消全选' : '全选';
}

export function filterModels() {
    renderModelList(modalModels);
}

export async function detectSelectedModels() {
    if (selectedModels.size === 0) {
        showToast('请先选择要检测的模型', 'error');
        return;
    }

    const key = document.getElementById('manual-key').value.trim();
    const provider = document.getElementById('manual-provider').value;
    const concurrency = parseInt(document.getElementById('modal-concurrency-input').value) || 1;

    if (!key && !provider) {
        showToast('请先输入 Key 或选择服务商', 'error');
        return;
    }

    const detectBtn = document.getElementById('detect-selected-btn');
    detectBtn.disabled = true;
    detectBtn.textContent = '检测中...';

    // Mark all selected as checking
    for (const model of selectedModels) {
        const item = document.querySelector(`.model-detect-item[data-model="${model}"]`);
        if (item) {
            let statusEl = item.querySelector('.model-detect-status');
            if (!statusEl) {
                statusEl = document.createElement('span');
                statusEl.className = 'model-detect-status checking';
                statusEl.textContent = '检测中';
                item.appendChild(statusEl);
            } else {
                statusEl.className = 'model-detect-status checking';
                statusEl.textContent = '检测中';
            }
        }
    }

    let successCount = 0;
    let failCount = 0;

    for (const model of selectedModels) {
        const item = document.querySelector(`.model-detect-item[data-model="${model}"]`);

        try {
            const result = await safeFetch('/api/test/concurrency/model', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ key, provider: provider || '', model, concurrency })
            });

            if (result.error) {
                if (item) {
                    const statusEl = item.querySelector('.model-detect-status');
                    if (statusEl) {
                        statusEl.className = 'model-detect-status unavailable';
                        statusEl.textContent = '失败';
                    }
                }
                failCount++;
            } else {
                if (item) {
                    const statusEl = item.querySelector('.model-detect-status');
                    if (statusEl) {
                        statusEl.className = 'model-detect-status available';
                        statusEl.textContent = result.max_concurrency ? `${result.max_concurrency} 并发` : '可用';
                    }
                }
                successCount++;
            }
        } catch (e) {
            if (item) {
                const statusEl = item.querySelector('.model-detect-status');
                if (statusEl) {
                    statusEl.className = 'model-detect-status unavailable';
                    statusEl.textContent = '错误';
                }
            }
            failCount++;
        }
    }

    detectBtn.disabled = false;
    detectBtn.textContent = '检测可用';
    showToast(`检测完成: ${successCount} 可用, ${failCount} 失败`, 'success');
}

// Token Test for Selected Models
export async function runTokenTestForSelectedModels() {
    if (selectedModels.size === 0) {
        showToast('请先选择要测试的模型', 'error');
        return;
    }

    const key = document.getElementById('manual-key').value.trim();
    const provider = document.getElementById('manual-provider').value;

    if (!key && !provider) {
        showToast('请先输入 Key 或选择服务商', 'error');
        return;
    }

    const tokenBtn = document.getElementById('token-test-btn');
    tokenBtn.disabled = true;
    tokenBtn.textContent = '测试中...';

    // Mark all selected as checking
    for (const model of selectedModels) {
        const item = document.querySelector(`.model-detect-item[data-model="${model}"]`);
        if (item) {
            let statusEl = item.querySelector('.model-detect-status');
            if (!statusEl) {
                statusEl = document.createElement('span');
                statusEl.className = 'model-detect-status checking';
                statusEl.textContent = '测试中';
                item.appendChild(statusEl);
            } else {
                statusEl.className = 'model-detect-status checking';
                statusEl.textContent = '测试中';
            }
        }
    }

    let successCount = 0;
    let failCount = 0;

    for (const model of selectedModels) {
        const item = document.querySelector(`.model-detect-item[data-model="${model}"]`);

        try {
            const result = await safeFetch('/api/test/token/model', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ key, provider: provider || '', model })
            });

            if (result.error) {
                if (item) {
                    const statusEl = item.querySelector('.model-detect-status');
                    if (statusEl) {
                        statusEl.className = 'model-detect-status unavailable';
                        statusEl.textContent = '失败';
                    }
                }
                failCount++;
            } else {
                if (item) {
                    const statusEl = item.querySelector('.model-detect-status');
                    if (statusEl) {
                        statusEl.className = 'model-detect-status available';
                        statusEl.textContent = result.max_tokens ? `${result.max_tokens.toLocaleString()} tokens` : 'N/A';
                    }
                }
                successCount++;
            }
        } catch (e) {
            if (item) {
                const statusEl = item.querySelector('.model-detect-status');
                if (statusEl) {
                    statusEl.className = 'model-detect-status unavailable';
                    statusEl.textContent = '错误';
                }
            }
            failCount++;
        }
    }

    tokenBtn.disabled = false;
    tokenBtn.textContent = 'Token上限';
    showToast(`Token测试完成: ${successCount} 成功, ${failCount} 失败`, 'success');
}
