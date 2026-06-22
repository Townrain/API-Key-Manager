/**
 * Entry point — wires all modules together.
 * Exposes functions to window scope for inline onclick handlers,
 * sets up event listeners, and calls init functions.
 */

// ─── Module Imports ──────────────────────────────────────────────────────────

import { showToast } from './toast.js';
import { showProgress, updateProgress, hideProgress } from './progress.js';
import { showConfirm, confirmOk, confirmCancel } from './confirm.js';
import { renderKeys, filterKeys, updatePagination, changePageSize, goToPage, switchTab, toggleKeyDisplay, copyKey, deleteKey } from './keys-table.js';
import { toggleProviders, showProviderDetail, closeProviderDetailModal, populateProviderDropdown } from './providers.js';
import { showBatchResults } from './batch.js';
import { closeModal, copyExport, downloadExport, showModelsModal, closeModelsModal, showShortcutsModal, closeShortcutsModal, showSignatureReport, closeSignatureReportModal, renderSignatureReport, showAddProviderModal, closeAddProviderModal, submitAddProvider } from './modals.js';
import { openModelDetectModal, closeModelDetectModal, fetchModelsForModal, filterModelsByType, renderModelList, toggleModelSelection, selectAllModels, updateSelectAllButton, filterModels, detectSelectedModels, runTokenTestForSelectedModels } from './model-detect.js';
import {
    safeFetch, loadStats, loadKeys, loadProxy, loadLogs, loadProviders, clearLogs,
    exportValidKeys, checkManualKey, getModels, checkAvailableModels,
    checkBalance, runCheck, runTokenTestBatch, runConcurrencyTestBatch,
    runTokenTest, runConcurrencyTest, runBatchCheck, clearAllKeys,
    uploadFile, handleFileUpload
} from './api/index.js';
import { selectCustomOption, toggleCustomSelect, toggleLogs } from './ui-helpers.js';

// ─── Expose to window for inline onclick handlers ────────────────────────────

window.showToast = showToast;
window.showProgress = showProgress;
window.updateProgress = updateProgress;
window.hideProgress = hideProgress;
window.showConfirm = showConfirm;
window.confirmOk = confirmOk;
window.confirmCancel = confirmCancel;
window.renderKeys = renderKeys;
window.filterKeys = filterKeys;
window.updatePagination = updatePagination;
window.changePageSize = changePageSize;
window.goToPage = goToPage;
window.switchTab = switchTab;
window.toggleKeyDisplay = toggleKeyDisplay;
window.copyKey = copyKey;
window.deleteKey = deleteKey;
window.toggleProviders = toggleProviders;
window.showProviderDetail = showProviderDetail;
window.closeProviderDetailModal = closeProviderDetailModal;
window.showBatchResults = showBatchResults;
window.closeModal = closeModal;
window.copyExport = copyExport;
window.downloadExport = downloadExport;
window.showModelsModal = showModelsModal;
window.closeModelsModal = closeModelsModal;
window.showShortcutsModal = showShortcutsModal;
window.closeShortcutsModal = closeShortcutsModal;
window.showSignatureReport = showSignatureReport;
window.closeSignatureReportModal = closeSignatureReportModal;
window.renderSignatureReport = renderSignatureReport;
window.showAddProviderModal = showAddProviderModal;
window.closeAddProviderModal = closeAddProviderModal;
window.submitAddProvider = submitAddProvider;
window.openModelDetectModal = openModelDetectModal;
window.closeModelDetectModal = closeModelDetectModal;
window.fetchModelsForModal = fetchModelsForModal;
window.filterModelsByType = filterModelsByType;
window.renderModelList = renderModelList;
window.toggleModelSelection = toggleModelSelection;
window.selectAllModels = selectAllModels;
window.updateSelectAllButton = updateSelectAllButton;
window.filterModels = filterModels;
window.detectSelectedModels = detectSelectedModels;
window.runTokenTestForSelectedModels = runTokenTestForSelectedModels;

// API functions
window.safeFetch = safeFetch;
window.loadStats = loadStats;
window.loadKeys = loadKeys;
window.loadProxy = loadProxy;
window.loadLogs = loadLogs;
window.loadProviders = loadProviders;
window.clearLogs = clearLogs;
window.exportValidKeys = exportValidKeys;
window.checkManualKey = checkManualKey;
window.getModels = getModels;
window.checkAvailableModels = checkAvailableModels;
window.checkBalance = checkBalance;
window.runCheck = runCheck;
window.runTokenTestBatch = runTokenTestBatch;
window.runConcurrencyTestBatch = runConcurrencyTestBatch;
window.runTokenTest = runTokenTest;
window.runConcurrencyTest = runConcurrencyTest;
window.runBatchCheck = runBatchCheck;
window.clearAllKeys = clearAllKeys;
window.uploadFile = uploadFile;
window.handleFileUpload = handleFileUpload;

window.selectCustomOption = selectCustomOption;
window.toggleCustomSelect = toggleCustomSelect;
window.toggleLogs = toggleLogs;

window.populateProviderDropdown = populateProviderDropdown;

// ─── Event Listeners ─────────────────────────────────────────────────────────

// Global error handler - prevents silent JS errors from breaking the UI
window.addEventListener('error', function(e) {
    console.error('[KeyHub] Uncaught error:', e.message, 'at', e.filename + ':' + e.lineno);
    e.preventDefault();
});
window.addEventListener('unhandledrejection', function(e) {
    console.error('[KeyHub] Unhandled promise rejection:', e.reason);
    e.preventDefault();
});

// Event delegation fallback - ensures clicks work even if inline handlers are blocked
document.addEventListener('click', function(e) {
    const target = e.target;
    // Provider chips in the grid
    const chipItem = target.closest('.provider-chip-item[data-provider]');
    if (chipItem) {
        e.preventDefault();
        const prov = chipItem.getAttribute('data-provider');
        if (prov && typeof showProviderDetail === 'function') showProviderDetail(prov);
        return;
    }
    // Provider chips in the table
    const provChip = target.closest('.provider-chip');
    if (provChip) {
        e.preventDefault();
        const m = provChip.getAttribute('onclick');
        if (m) { const p = m.match(/showProviderDetail\('(.+?)'\)/); if (p) showProviderDetail(p[1]); }
        return;
    }
    // Key cells in the table
    const keyCell = target.closest('.key-cell');
    if (keyCell) {
        e.preventDefault();
        const m = keyCell.getAttribute('onclick');
        if (m) { const p = m.match(/copyKey\('(.+?)'\)/); if (p) copyKey(p[1]); }
        return;
    }
    // Nav tabs
    const navTab = target.closest('.nav-tab[data-tab]');
    if (navTab) {
        const tab = navTab.getAttribute('data-tab');
        if (tab && tab !== 'signature' && typeof switchTab === 'function') {
            e.preventDefault();
            switchTab(tab);
        }
        return;
    }
}, true);

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'r') { e.preventDefault(); loadKeys(); loadStats(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); runCheck(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); toggleKeyDisplay(); }
    if (e.key === 'Escape') {
        const si = document.getElementById('search-input');
        if (si === document.activeElement) { si.value = ''; filterKeys(); }
        closeShortcutsModal();
        closeProviderDetailModal();
        closeSignatureReportModal();
        confirmCancel();
    }
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') { e.preventDefault(); document.getElementById('search-input').focus(); }
    if (e.key === '?' && document.activeElement.tagName !== 'INPUT') { e.preventDefault(); showShortcutsModal(); }
});

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-select')) {
        document.querySelectorAll('.custom-select.open').forEach(el => {
            el.classList.remove('open');
        });
    }
});

// Modal backdrop clicks
document.addEventListener('DOMContentLoaded', () => {
    { const el = document.getElementById('shortcuts-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeShortcutsModal(); }); }
    { const el = document.getElementById('confirm-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) confirmCancel(); }); }
    { const el = document.getElementById('provider-detail-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeProviderDetailModal(); }); }
    { const el = document.getElementById('signature-report-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeSignatureReportModal(); }); }
    { const el = document.getElementById('export-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeModal(); }); }
    { const el = document.getElementById('models-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeModelsModal(); }); }
    { const el = document.getElementById('model-detect-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeModelDetectModal(); }); }
    { const el = document.getElementById('add-provider-modal'); if (el) el.addEventListener('click', (e) => { if (e.target === el) closeAddProviderModal(); }); }

    // Provider filter change
    { const el = document.getElementById('provider-filter'); if (el) el.addEventListener('change', () => loadKeys(1)); }

    // Manual key input enter
    document.getElementById('manual-key')?.addEventListener('keypress', (e) => { if (e.key === 'Enter') checkManualKey(); });

    // Upload zone drag & drop
    const uz = document.getElementById('upload-zone');
    if (uz) {
        uz.addEventListener('dragover', (e) => { e.preventDefault(); uz.style.borderColor = 'var(--neon-cyan)'; uz.style.background = 'var(--glow-cyan)'; });
        uz.addEventListener('dragleave', () => { uz.style.borderColor = ''; uz.style.background = ''; });
        uz.addEventListener('drop', (e) => { e.preventDefault(); uz.style.borderColor = ''; uz.style.background = ''; const f = e.dataTransfer.files[0]; if (f && f.name.endsWith('.json')) uploadFile(f); else showToast('请上传 .json 文件', 'error'); });
    }
});

// ─── Init Calls ──────────────────────────────────────────────────────────────

loadStats(); loadKeys(); loadProxy(); loadLogs(); loadProviders();
