import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cloud, ArrowRight, ExternalLink, BookOpen, RefreshCw,
  Plus, Pencil, Trash2, Wifi, AlertCircle, CheckCircle, XCircle, Loader2,
} from 'lucide-react';
import type { Colors } from '../theme/tokens';
import { api, type ProviderInfo, type ProviderDetail, type ProviderConfig, type ProviderCreateBody, type ProviderTestResult } from '../api/client';
import { ConfirmDialog } from '../components/ConfirmDialog';

const isTauri = typeof window !== 'undefined' && '__TAURI__' in window;

async function openUrl(url: string) {
  if (isTauri) {
    const { open } = await import('@tauri-apps/plugin-shell');
    await open(url);
  } else {
    window.open(url, '_blank');
  }
}

interface Props {
  colors: Colors;
  visible?: boolean;
  onNavigateToKeys?: (provider: string) => void;
}

export function ProvidersPage({ colors: c, visible, onNavigateToKeys }: Props) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [details, setDetails] = useState<ProviderDetail[]>([]);
  const [selected, setSelected] = useState<ProviderInfo | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ProviderDetail | null>(null);
  const [selectedConfig, setSelectedConfig] = useState<ProviderConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [spins, setSpins] = useState(0);

  // CRUD state
  const [editMode, setEditMode] = useState<'create' | 'edit' | null>(null);
  const [editForm, setEditForm] = useState<ProviderCreateBody>({ name: '', base_url: '', check_endpoint: '' });
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Test state
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);
  const [testKey, setTestKey] = useState('');

  // Toast
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), type === 'error' ? 4000 : 2500);
  };

  // Track custom provider names
  const [customNames, setCustomNames] = useState<Set<string>>(new Set());

  const load = () => {
    setSpins(s => s + 1);
    setLoading(true);
    Promise.all([
      api.getProviders().then(setProviders),
      api.getProviderDetails().then(setDetails),
    ]).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  // Refresh data when page becomes visible
  const prevVisible = useRef(false);
  useEffect(() => {
    if (visible && !prevVisible.current) {
      load();
    }
    prevVisible.current = visible ?? false;
  }, [visible]);

  const showDetail = async (p: ProviderInfo) => {
    setSelected(p);
    setSelectedDetail(details.find(d => d.name === p.name) || null);
    setTestResult(null);
    setTestKey('');
    try {
      const cfg = await api.getProvider(p.name);
      setSelectedConfig(cfg);
      if (cfg.source === 'custom') {
        setCustomNames(prev => new Set([...prev, p.name]));
      }
    } catch {
      setSelectedConfig(null);
    }
  };

  const closeDetail = () => {
    setSelected(null);
    setSelectedConfig(null);
    setTestResult(null);
    setTestKey('');
  };

  // Test connectivity
  const handleTest = async () => {
    if (!selected) return;
    if (!testKey.trim()) {
      setTestResult({ success: false, provider: selected.name, error: '请输入 API Key 进行真实连接测试' });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const r = await api.testProviderConnectivity(selected.name, testKey.trim());
      setTestResult(r);
    } catch (e: any) {
      setTestResult({ success: false, provider: selected.name, error: e.message });
    } finally {
      setTesting(false);
    }
  };

  // Create provider
  const openCreate = () => {
    setEditMode('create');
    setEditForm({ name: '', base_url: '', check_endpoint: '' });
    setEditError('');
  };

  // Edit provider
  const openEdit = async () => {
    if (!selected || !selectedConfig) return;
    setEditMode('edit');
    setEditForm({
      name: selectedConfig.name,
      base_url: selectedConfig.base_url,
      check_endpoint: selectedConfig.check_endpoint,
      chat_endpoint: selectedConfig.chat_endpoint || '',
      key_prefixes: selectedConfig.key_prefixes || [],
      error_signatures: selectedConfig.error_signatures || [],
      website_url: selectedConfig.website_url || '',
      docs_url: selectedConfig.docs_url || '',
    });
    setEditError('');
  };

  const submitEdit = async () => {
    if (!editForm.name.trim() || !editForm.base_url.trim() || !editForm.check_endpoint.trim()) {
      setEditError('名称、Base URL 和检测端点为必填项');
      return;
    }
    setEditLoading(true);
    setEditError('');
    try {
      if (editMode === 'create') {
        await api.createProvider(editForm);
        showToast(`服务商 "${editForm.name}" 创建成功`);
      } else {
        await api.updateProvider(editForm.name, editForm);
        showToast(`服务商 "${editForm.name}" 更新成功`);
      }
      setEditMode(null);
      load();
    } catch (e: any) {
      setEditError(e.message);
    } finally {
      setEditLoading(false);
    }
  };

  // Delete provider
  const handleDelete = async (name: string) => {
    try {
      await api.deleteProvider(name);
      showToast(`服务商 "${name}" 已删除`);
      setConfirmDelete(null);
      closeDetail();
      load();
    } catch (e: any) {
      showToast(`删除失败: ${e.message}`, 'error');
    }
  };

  const isCustom = (name: string) => customNames.has(name);

  return (
    <div style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0, 0, 0.2, 1] }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: c.textPrimary, margin: 0, letterSpacing: -0.5 }}>服务商</h1>
            <p style={{ fontSize: 13, color: c.textTertiary, margin: '4px 0 0' }}>已支持的 API 服务商列表</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <motion.button
              whileHover={{ y: 2 }}
              whileTap={{ scale: 0.97 }}
              transition={{
                y: { duration: 0.35, ease: [0, 0, 0.2, 1] },
                scale: { type: 'spring', damping: 20, stiffness: 400 },
              }}
              onClick={openCreate}
              style={{
                padding: '8px 14px', borderRadius: 8,
                border: 'none',
                background: c.primary, color: c.onPrimary,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
                fontSize: 12, fontWeight: 600,
              }}
            >
              <Plus size={14} />
              新建服务商
            </motion.button>
            <motion.button
              whileHover={{ y: 2 }}
              whileTap={{ scale: 0.97 }}
              transition={{
                y: { duration: 0.35, ease: [0, 0, 0.2, 1] },
                scale: { type: 'spring', damping: 20, stiffness: 400 },
              }}
              onClick={load}
              style={{
                padding: 8, borderRadius: 8,
                border: `1px solid ${c.borderSubtle}`,
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 150ms ease, border-color 150ms ease',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = c.surfaceHover;
                e.currentTarget.style.borderColor = c.border;
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.borderColor = c.borderSubtle;
              }}
            >
              <motion.div
                animate={{ rotate: spins * 360 }}
                transition={{ duration: 0.6, ease: [0.68, -0.55, 0.265, 1.55] }}
              >
                <RefreshCw size={18} color={c.textSecondary} />
              </motion.div>
            </motion.button>
          </div>
        </div>
      </motion.div>

      <div style={{ height: 24 }} />

      {/* Grid */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
              style={{
                width: 32, height: 32, borderRadius: '50%',
                border: `3px solid ${c.primary}30`, borderTopColor: c.primary,
                animation: 'spin 1s linear infinite',
              }}
            />
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: 12,
          }}>
            {providers.map((p, i) => (
              <ProviderCard
                key={p.name}
                colors={c}
                provider={p}
                index={i}
                isCustom={isCustom(p.name)}
                onTap={() => showDetail(p)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail Dialog */}
      <AnimatePresence>
        {selected && (
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={selected.display_name}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeDetail}
            onKeyDown={e => e.key === 'Escape' && closeDetail()}
            style={{
              position: 'fixed', inset: 0, zIndex: 100,
              background: 'rgba(0,0,0,0.5)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.92, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              onClick={e => e.stopPropagation()}
              style={{
                background: c.surface, borderRadius: 16,
                padding: 28, width: 460, maxWidth: '90vw',
                maxHeight: '85vh', overflow: 'auto',
              }}
            >
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 10,
                  background: c.primaryGlow,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Cloud size={20} color={c.primary} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>{selected.display_name}</div>
                    {isCustom(selected.name) && (
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                        background: `${c.info}1F`, color: c.info,
                      }}>自定义</span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, fontFamily: 'Consolas', color: c.textTertiary }}>{selected.name}</div>
                </div>
              </div>

              {/* Details */}
              {selectedDetail && (
                <div style={{ marginBottom: 20 }}>
                  {selectedDetail.prefix && (
                    <div style={{ display: 'flex', marginBottom: 10 }}>
                      <div style={{ width: 80, fontSize: 12, fontWeight: 500, color: c.textTertiary }}>Key 前缀</div>
                      <code style={{ fontSize: 13, fontFamily: 'Consolas', color: c.textPrimary }}>{selectedDetail.prefix}</code>
                    </div>
                  )}
                  {selectedDetail.base_url && (
                    <div style={{ display: 'flex', marginBottom: 10 }}>
                      <div style={{ width: 80, fontSize: 12, fontWeight: 500, color: c.textTertiary }}>Base URL</div>
                      <code style={{ fontSize: 13, fontFamily: 'Consolas', color: c.textPrimary, wordBreak: 'break-all' }}>{selectedDetail.base_url}</code>
                    </div>
                  )}
                  {selectedConfig?.check_endpoint && (
                    <div style={{ display: 'flex', marginBottom: 10 }}>
                      <div style={{ width: 80, fontSize: 12, fontWeight: 500, color: c.textTertiary }}>检测端点</div>
                      <code style={{ fontSize: 13, fontFamily: 'Consolas', color: c.textPrimary, wordBreak: 'break-all' }}>{selectedConfig.check_endpoint}</code>
                    </div>
                  )}
                  {selectedDetail.website_url && (
                    <div style={{ display: 'flex', marginBottom: 10 }}>
                      <div style={{ width: 80, fontSize: 12, fontWeight: 500, color: c.textTertiary }}>官网</div>
                      <span
                        onClick={() => openUrl(selectedDetail.website_url!)}
                        style={{ fontSize: 13, color: c.primary, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}
                        onMouseEnter={e => { e.currentTarget.style.textDecoration = 'underline'; }}
                        onMouseLeave={e => { e.currentTarget.style.textDecoration = 'none'; }}
                      >
                        {selectedDetail.website_name || selectedDetail.website_url}
                        <ExternalLink size={12} />
                      </span>
                    </div>
                  )}
                  {selectedDetail.docs_url && (
                    <div style={{ display: 'flex', marginBottom: 10 }}>
                      <div style={{ width: 80, fontSize: 12, fontWeight: 500, color: c.textTertiary }}>文档</div>
                      <span
                        onClick={() => openUrl(selectedDetail.docs_url!)}
                        style={{ fontSize: 13, color: c.primary, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}
                        onMouseEnter={e => { e.currentTarget.style.textDecoration = 'underline'; }}
                        onMouseLeave={e => { e.currentTarget.style.textDecoration = 'none'; }}
                      >
                        <BookOpen size={12} />
                        API 文档
                        <ExternalLink size={12} />
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Test result */}
              {testResult && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', damping: 12, stiffness: 200 }}
                  style={{
                    padding: 12, borderRadius: 8, marginBottom: 16,
                    background: testResult.success ? `${c.success}0A` : `${c.error}0A`,
                    border: `1px solid ${testResult.success ? `${c.success}33` : `${c.error}33`}`,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    {testResult.success
                      ? <CheckCircle size={16} color={c.success} />
                      : <XCircle size={16} color={c.error} />}
                    <span style={{ fontSize: 13, fontWeight: 600, color: testResult.success ? c.success : c.error }}>
                      {testResult.success ? '连接成功' : '连接失败'}
                    </span>
                  </div>
                  {testResult.success && testResult.models_count != null && (
                    <div style={{ fontSize: 12, color: c.textTertiary, marginTop: 4 }}>
                      发现 {testResult.models_count} 个模型
                      {testResult.sample_models && testResult.sample_models.length > 0 && (
                        <span>: {testResult.sample_models.join(', ')}</span>
                      )}
                    </div>
                  )}
                  {testResult.error && (
                    <div style={{ fontSize: 12, color: c.error, marginTop: 4 }}>{testResult.error}</div>
                  )}
                </motion.div>
              )}

              {/* Test key input */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, fontWeight: 500, color: c.textSecondary, marginBottom: 6 }}>
                  API Key（用于真实连通性测试）
                </div>
                <input
                  value={testKey}
                  onChange={e => setTestKey(e.target.value)}
                  placeholder="输入该服务商的 API Key"
                  type="password"
                  style={{
                    width: '100%', padding: '8px 12px', borderRadius: 8,
                    border: `1.5px solid ${c.borderSubtle}`,
                    background: c.surfaceLow,
                    color: c.textPrimary, fontSize: 13, outline: 'none',
                    fontFamily: 'Consolas',
                    transition: 'border-color 200ms ease',
                  }}
                  onFocus={e => e.currentTarget.style.borderColor = c.primary}
                  onBlur={e => e.currentTarget.style.borderColor = c.borderSubtle}
                />
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                  onClick={handleTest}
                  disabled={testing}
                  style={{
                    padding: '8px 14px', borderRadius: 8,
                    border: 'none', background: `${c.info}1A`, color: c.info,
                    fontSize: 12, fontWeight: 600, cursor: testing ? 'wait' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: 6,
                    opacity: testing ? 0.7 : 1,
                  }}
                >
                  {testing ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Wifi size={14} />}
                  {testing ? '测试中...' : '测试连通性'}
                </motion.button>

                {isCustom(selected.name) && (
                  <>
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                      onClick={openEdit}
                      style={{
                        padding: '8px 14px', borderRadius: 8,
                        border: 'none', background: `${c.primary}1A`, color: c.primary,
                        fontSize: 12, fontWeight: 600, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      <Pencil size={14} />
                      编辑
                    </motion.button>
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                      onClick={() => setConfirmDelete(selected.name)}
                      style={{
                        padding: '8px 14px', borderRadius: 8,
                        border: 'none', background: `${c.error}1A`, color: c.error,
                        fontSize: 12, fontWeight: 600, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      <Trash2 size={14} />
                      删除
                    </motion.button>
                  </>
                )}

                <div style={{ flex: 1 }} />

                <motion.button
                  whileTap={{ scale: 0.97 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                  onClick={closeDetail}
                  style={{
                    padding: '10px 20px', borderRadius: 8,
                    border: 'none', background: 'transparent',
                    color: c.textTertiary, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  }}
                >关闭</motion.button>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                  onClick={() => {
                    closeDetail();
                    onNavigateToKeys?.(selected.name);
                  }}
                  style={{
                    padding: '10px 20px', borderRadius: 8,
                    border: 'none', background: c.primary, color: c.onPrimary,
                    fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  查看密钥
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create/Edit Dialog */}
      <AnimatePresence>
        {editMode && (
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setEditMode(null)}
            onKeyDown={e => e.key === 'Escape' && setEditMode(null)}
            style={{
              position: 'fixed', inset: 0, zIndex: 110,
              background: 'rgba(0,0,0,0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              onClick={e => e.stopPropagation()}
              style={{
                background: c.surface, borderRadius: 16,
                padding: 28, width: 480, maxWidth: '90vw',
                maxHeight: '85vh', overflow: 'auto',
                boxShadow: `0 20px 60px ${c.shadow}`,
              }}
            >
              <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary, marginBottom: 20 }}>
                {editMode === 'create' ? '新建服务商' : '编辑服务商'}
              </div>

              <ProviderForm colors={c} form={editForm} onChange={setEditForm} disabled={editMode === 'edit'} />

              {editError && (
                <div style={{
                  marginTop: 12, padding: '8px 12px', borderRadius: 8,
                  background: `${c.error}0A`, border: `1px solid ${c.error}33`,
                  fontSize: 12, color: c.error, display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <AlertCircle size={14} />
                  {editError}
                </div>
              )}

              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 20 }}>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                  onClick={() => setEditMode(null)}
                  style={{
                    padding: '10px 16px', borderRadius: 8,
                    border: 'none', background: 'transparent',
                    color: c.textTertiary, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  }}
                >取消</motion.button>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                  onClick={submitEdit}
                  disabled={editLoading}
                  style={{
                    padding: '10px 24px', borderRadius: 8,
                    border: 'none', background: c.primary, color: c.onPrimary,
                    fontSize: 13, fontWeight: 600, cursor: editLoading ? 'wait' : 'pointer',
                    opacity: editLoading ? 0.7 : 1,
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}
                >
                  {editLoading && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
                  {editMode === 'create' ? '创建' : '保存'}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirm Delete Dialog */}
      <AnimatePresence>
        {confirmDelete && (
          <ConfirmDialog
            colors={c}
            title="删除服务商"
            desc={`确定要删除自定义服务商 "${confirmDelete}" 吗？此操作不可恢复。`}
            confirmLabel="删除"
            destructive
            onConfirm={() => handleDelete(confirmDelete)}
            onCancel={() => setConfirmDelete(null)}
          />
        )}
      </AnimatePresence>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={{ type: 'spring', stiffness: 300, damping: 15 }}
            style={{
              position: 'fixed', bottom: 32, left: 32, right: 32,
              zIndex: 200,
              padding: '14px 18px', borderRadius: 10,
              background: toast.type === 'error' ? c.error : c.success,
              color: '#fff', fontSize: 13, fontWeight: 600,
              boxShadow: `0 6px 16px ${toast.type === 'error' ? c.error : c.success}59`,
            }}
          >
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── ProviderCard (matches Flutter _ProviderCard) ──────────────────────────

function ProviderCard({ colors: c, provider, index, isCustom, onTap }: {
  colors: Colors; provider: ProviderInfo; index: number; isCustom: boolean; onTap: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: 3 }}
      whileTap={{ scale: 0.97 }}
      transition={{
        opacity: { duration: 0.25, delay: index * 0.03 },
        y: { duration: 0.35, ease: [0, 0, 0.2, 1] },
        scale: { type: 'spring', damping: 20, stiffness: 400 },
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onTap}
      style={{
        padding: '14px 16px', borderRadius: 10, cursor: 'pointer',
        background: hovered ? c.surfaceHover : c.surface,
        border: `1px solid ${hovered ? `${c.primary}40` : c.borderSubtle}`,
        boxShadow: hovered ? `0 6px 18px ${c.shadow}` : 'none',
        transition: 'border 250ms cubic-bezier(0.25,0.46,0.45,0.94), box-shadow 250ms cubic-bezier(0.25,0.46,0.45,0.94), background 250ms cubic-bezier(0.25,0.46,0.45,0.94)',
        display: 'flex', alignItems: 'center', gap: 14,
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 8,
        background: hovered ? `${c.primary}2E` : c.primaryGlow,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
        transition: 'background 250ms ease',
      }}>
        <Cloud size={18} color={c.primary} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {provider.display_name}
          </div>
          {isCustom && (
            <span style={{
              fontSize: 9, fontWeight: 600, padding: '1px 5px', borderRadius: 3,
              background: `${c.info}1F`, color: c.info, flexShrink: 0,
            }}>自定义</span>
          )}
        </div>
        <div style={{ fontSize: 11, color: c.textTertiary, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {provider.name}
        </div>
      </div>
      <motion.div
        animate={{ rotate: hovered ? 0 : -0.1 * (180 / Math.PI), x: hovered ? 2 : 0 }}
        transition={{ duration: 0.25, ease: [0.68, -0.55, 0.265, 1.55] }}
      >
        <ArrowRight size={12} color={hovered ? c.primary : `${c.textTertiary}4D`} />
      </motion.div>
    </motion.div>
  );
}

// ─── ProviderForm ─────────────────────────────────────────────────────────

function ProviderForm({ colors: c, form, onChange, disabled }: {
  colors: Colors;
  form: ProviderCreateBody;
  onChange: (f: ProviderCreateBody) => void;
  disabled?: boolean;
}) {
  const [focused, setFocused] = useState<string | null>(null);

  const field = (label: string, key: keyof ProviderCreateBody, placeholder: string, required = false, extra?: React.CSSProperties) => (
    <div style={{ marginBottom: 14, ...extra }}>
      <label style={{ fontSize: 12, fontWeight: 500, color: c.textSecondary, display: 'block', marginBottom: 6 }}>
        {label} {required && <span style={{ color: c.error }}>*</span>}
      </label>
      <input
        disabled={disabled}
        value={(form[key] as string) || ''}
        onChange={e => onChange({ ...form, [key]: e.target.value })}
        onFocus={() => setFocused(key)}
        onBlur={() => setFocused(null)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '8px 14px', borderRadius: 8,
          border: `1.5px solid ${focused === key ? c.primary : c.borderSubtle}`,
          background: disabled ? c.surfaceHover : c.surfaceLow,
          color: c.textPrimary, fontSize: 13, outline: 'none',
          fontFamily: 'Consolas',
          transition: 'border-color 200ms ease',
          boxShadow: focused === key ? `0 0 0 3px ${c.primary}1A` : 'none',
          opacity: disabled ? 0.6 : 1,
        }}
      />
    </div>
  );

  return (
    <div>
      {field('服务商名称', 'name', '例如: my-custom-provider', true)}
      {field('Base URL', 'base_url', 'https://api.example.com/v1', true)}
      {field('检测端点', 'check_endpoint', '/models (用于验证密钥)', true)}
      {field('对话端点', 'chat_endpoint', '/chat/completions (可选)')}
      {field('官网 URL', 'website_url', 'https://example.com (可选)')}
      {field('文档 URL', 'docs_url', 'https://docs.example.com (可选)')}
    </div>
  );
}
