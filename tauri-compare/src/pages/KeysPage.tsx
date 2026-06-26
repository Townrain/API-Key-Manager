import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, ChevronLeft, ChevronRight, Copy, Check, Plus,
  RefreshCw, CloudOff, KeyRound, Upload, X, Cloud, AlertCircle,
  CheckCircle, XCircle, HelpCircle, Filter, Trash2,
} from 'lucide-react';
import type { Colors } from '../theme/tokens';
import { api, type KeyInfo, type ProviderInfo } from '../api/client';
import { ImportDialog } from '../components/ImportDialog';
import { ConfirmDialog } from '../components/ConfirmDialog';

interface Props {
  colors: Colors;
  visible?: boolean;
  providerFilter?: string | null;
  onImportSuccess?: (fileName: string, newCount: number, dupeCount: number) => void;
}

const PAGE_SIZES = [25, 50, 100, 200];

const STATUS_CHIPS = [
  { val: null, label: '全部', icon: Filter },
  { val: 'valid', label: '有效', icon: CheckCircle },
  { val: 'invalid', label: '无效', icon: XCircle },
  { val: 'error', label: '错误', icon: HelpCircle },
  { val: 'unknown', label: '未知', icon: HelpCircle },
];

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  valid: { label: '有效', color: 'success' },
  invalid: { label: '无效', color: 'error' },
  checking: { label: '检测中', color: 'warning' },
  error: { label: '错误', color: 'error' },
};

const spring = { type: 'spring' as const, damping: 20, stiffness: 400 };

// ─── Toast ─────────────────────────────────────────────────────────────

interface ToastData {
  id: number;
  type: 'success' | 'error';
  message: string;
  detail?: string;
}

let toastId = 0;

function ToastContainer({ toasts, onDismiss, colors: c }: {
  toasts: ToastData[]; onDismiss: (id: number) => void; colors: Colors;
}) {
  return (
    <div style={{ position: 'fixed', top: 20, right: 20, zIndex: 1000, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 40, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.95 }}
            transition={{ type: 'spring', damping: 20, stiffness: 300 }}
            style={{
              padding: '12px 16px', borderRadius: 10, minWidth: 260, maxWidth: 380,
              background: t.type === 'success' ? `${c.success}14` : `${c.error}14`,
              border: `1px solid ${t.type === 'success' ? `${c.success}40` : `${c.error}40`}`,
              boxShadow: `0 8px 24px ${c.shadow}`,
              display: 'flex', alignItems: 'flex-start', gap: 10,
              cursor: 'pointer',
            }}
            onClick={() => onDismiss(t.id)}
          >
            {t.type === 'success'
              ? <CheckCircle size={18} color={c.success} style={{ flexShrink: 0, marginTop: 1 }} />
              : <XCircle size={18} color={c.error} style={{ flexShrink: 0, marginTop: 1 }} />
            }
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary }}>{t.message}</div>
              {t.detail && <div style={{ fontSize: 12, color: c.textTertiary, marginTop: 2 }}>{t.detail}</div>}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ─── HoverPress wrapper ────────────────────────────────────────────────

function HoverPress({ children, style: extraStyle }: { children: React.ReactNode; style?: React.CSSProperties }) {
  const [hovered, setHovered] = useState(false);
  return (
    <motion.div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      animate={{ y: hovered ? 1.5 : 0 }}
      transition={spring}
      style={extraStyle}
    >
      {children}
    </motion.div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────

export function KeysPage({ colors: c, visible, providerFilter, onImportSuccess }: Props) {
  const [keys, setKeys] = useState<KeyInfo[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const [filterProvider, setFilterProvider] = useState<string | null>(providerFilter ?? null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [checkingKey, setCheckingKey] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const [refreshSpinning, setRefreshSpinning] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const [singleKeyInput, setSingleKeyInput] = useState('');
  const [addingSingle, setAddingSingle] = useState(false);

  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Search debounce 300ms
  const onSearchChange = useCallback((val: string) => {
    setSearch(val);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => setDebouncedSearch(val), 300);
  }, []);

  useEffect(() => {
    return () => { if (searchTimerRef.current) clearTimeout(searchTimerRef.current); };
  }, []);

  useEffect(() => {
    if (providerFilter) setFilterProvider(providerFilter);
  }, [providerFilter]);

  const toastTimersRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  useEffect(() => () => { toastTimersRef.current.forEach(clearTimeout); toastTimersRef.current.clear(); }, []);

  const addToast = useCallback((type: 'success' | 'error', message: string, detail?: string) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, type, message, detail }]);
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      toastTimersRef.current.delete(timer);
    }, type === 'success' ? 3000 : 5000);
    toastTimersRef.current.add(timer);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.getKeys({
        provider: filterProvider ?? undefined,
        status: filterStatus ?? undefined,
        page,
        page_size: pageSize,
      });
      setKeys(res.keys);
      setTotal(res.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [page, filterProvider, filterStatus, pageSize]);

  useEffect(() => {
    api.getProviders().then(setProviders).catch(() => {});
  }, []);

  useEffect(() => { loadKeys(); }, [loadKeys]);

  // Refresh data when page becomes visible
  const prevVisible = useRef(false);
  useEffect(() => {
    if (visible && !prevVisible.current) {
      loadKeys();
      api.getProviders().then(setProviders).catch(() => {});
    }
    prevVisible.current = visible ?? false;
  }, [visible, loadKeys]);

  // Wider search: key_masked, provider, display_name from provider list
  const filtered = debouncedSearch
    ? keys.filter(k => {
        const q = debouncedSearch.toLowerCase();
        const dn = providers.find(p => p.name === k.provider)?.display_name || '';
        return (k.key_masked && k.key_masked.toLowerCase().includes(q)) ||
          k.provider.toLowerCase().includes(q) ||
          dn.toLowerCase().includes(q);
      })
    : keys;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const copyFullKey = async (keyMasked: string) => {
    try {
      const res = await api.revealKeyByMasked(keyMasked);
      await navigator.clipboard.writeText(res.key);
      setCopiedKey(keyMasked);
      setTimeout(() => setCopiedKey(null), 1500);
    } catch (e: any) {
      addToast('error', '复制失败', e.message);
    }
  };

  const checkSingle = async (key: string) => {
    setCheckingKey(key);
    try {
      const result = await api.checkKey(key);
      if (result.status === 'valid') {
        addToast('success', '密钥有效', result.latency_ms ? `延迟 ${result.latency_ms}ms` : undefined);
      } else {
        addToast('error', '密钥无效', result.error || `状态: ${result.status}`);
      }
      loadKeys();
    } catch (e: any) {
      addToast('error', '检测失败', e.message);
    } finally {
      setCheckingKey(null);
    }
  };

  const doDeleteKey = async (key: string) => {
    setConfirmDelete(null);
    try {
      await api.deleteKey(key);
      addToast('success', '已删除密钥');
      loadKeys();
    } catch (e: any) {
      addToast('error', '删除失败', e.message);
    }
  };

  const doClearAll = async () => {
    setConfirmClearAll(false);
    try {
      await api.clearKeys();
      addToast('success', '已清空所有密钥');
      loadKeys();
    } catch (e: any) {
      addToast('error', '清空失败', e.message);
    }
  };

  const addSingleKey = async () => {
    const key = singleKeyInput.trim();
    if (!key) return;
    setAddingSingle(true);
    try {
      const res = await api.importSingleKey(key);
      if (res.new > 0) {
        addToast('success', '密钥已添加');
      } else if (res.duplicates > 0) {
        addToast('error', '密钥已存在');
      } else if (res.errors.length > 0) {
        addToast('error', '添加失败', res.errors[0]);
      }
      setSingleKeyInput('');
      loadKeys();
    } catch (e: any) {
      addToast('error', '添加失败', e.message);
    } finally {
      setAddingSingle(false);
    }
  };

  const getStatusStyle = (status: string) => {
    const s = STATUS_MAP[status];
    if (!s) return { bg: c.surfaceLow, fg: c.textTertiary, label: '未知' };
    const colorVal = (c as Record<string, string>)[s.color] || c.textTertiary;
    return { bg: `${colorVal}1F`, fg: colorVal, label: s.label };
  };

  const handleRefresh = async () => {
    setRefreshSpinning(true);
    await loadKeys();
    setTimeout(() => setRefreshSpinning(false), 700);
  };

  return (
    <div style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} colors={c} />

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0, 0, 0.2, 1] }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: c.textPrimary, margin: 0, letterSpacing: -0.5 }}>密钥管理</h1>
            <p style={{ fontSize: 13, color: c.textTertiary, margin: '4px 0 0' }}>查看、搜索、验证密钥</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Single key input */}
            <input
              value={singleKeyInput}
              onChange={e => setSingleKeyInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addSingleKey()}
              placeholder="输入密钥快速添加..."
              disabled={addingSingle}
              style={{
                width: 220, padding: '6px 12px', borderRadius: 8,
                border: `1px solid ${c.borderSubtle}`, background: c.surfaceLow,
                color: c.textPrimary, fontSize: 12, outline: 'none',
                fontFamily: 'Consolas',
                transition: 'border-color 200ms ease',
              }}
              onFocus={e => { e.currentTarget.style.borderColor = c.primary; }}
              onBlur={e => { e.currentTarget.style.borderColor = c.borderSubtle; }}
            />
            <HoverPress>
              <motion.div
                whileTap={{ scale: 0.88 }}
                transition={spring}
                onClick={addSingleKey}
                style={{
                  padding: '6px 12px', borderRadius: 8, cursor: addingSingle ? 'wait' : 'pointer',
                  border: `1px solid ${c.primary}33`,
                  background: `${c.primary}14`, color: c.primary,
                  fontSize: 12, fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 4,
                  opacity: addingSingle || !singleKeyInput.trim() ? 0.5 : 1,
                  transition: 'all 150ms ease',
                }}
              >
                <Plus size={14} />
                添加
              </motion.div>
            </HoverPress>

            {/* Clear all button */}
            {keys.length > 0 && (
              <HoverPress>
                <motion.div
                  whileTap={{ scale: 0.88 }}
                  transition={spring}
                  onClick={() => setConfirmClearAll(true)}
                  title="清空所有密钥"
                  style={{
                    padding: '6px 12px', borderRadius: 8, cursor: 'pointer',
                    border: `1px solid ${c.error}33`,
                    background: `${c.error}14`, color: c.error,
                    fontSize: 12, fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: 6,
                    transition: 'all 150ms ease',
                  }}
                >
                  <Trash2 size={14} />
                  清空
                </motion.div>
              </HoverPress>
            )}

            {/* Refresh with spin */}
            <HoverPress>
              <motion.div
                whileTap={{ scale: 0.88 }}
                transition={spring}
                onClick={handleRefresh}
                title="刷新"
                style={{
                  width: 34, height: 34, borderRadius: 8, cursor: 'pointer',
                  border: `1px solid ${c.borderSubtle}`, background: 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 150ms ease',
                }}
              >
                <motion.div
                  animate={{ rotate: refreshSpinning ? 360 : 0 }}
                  transition={{ duration: 0.7, ease: [0.68, -0.55, 0.265, 1.55] }}
                >
                  <RefreshCw size={18} color={c.textSecondary} />
                </motion.div>
              </motion.div>
            </HoverPress>
          </div>
        </div>
      </motion.div>

      <div style={{ height: 20 }} />

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.15 }}
        style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}
      >
        {/* Status chips */}
        {STATUS_CHIPS.map((s) => (
          <FilterChip
            key={s.label}
            colors={c}
            label={s.label}
            icon={s.icon}
            selected={filterStatus === s.val}
            onTap={() => { setFilterStatus(s.val); setPage(1); }}
          />
        ))}

        <div style={{ width: 1 }} />

        {/* Provider dropdown */}
        {providers.length > 0 && (
          <ProviderDropdown
            colors={c}
            providers={providers}
            value={filterProvider}
            onChange={(v) => { setFilterProvider(v); setPage(1); }}
          />
        )}

        <div style={{ flex: 1 }} />

        {/* Search with clear button */}
        <div style={{ position: 'relative', minWidth: 320 }}>
          <Search size={17} color={c.textTertiary} style={{ position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
          <input
            value={search}
            onChange={e => onSearchChange(e.target.value)}
            placeholder="搜索密钥、服务商..."
            style={{
              width: '100%', padding: '10px 34px 10px 38px', borderRadius: 10,
              border: `1px solid ${c.borderSubtle}`, background: c.surfaceLow,
              color: c.textPrimary, fontSize: 14, outline: 'none',
              transition: 'border-color 200ms ease',
            }}
            onFocus={e => { e.currentTarget.style.borderColor = c.primary; }}
            onBlur={e => { e.currentTarget.style.borderColor = c.borderSubtle; }}
          />
          <AnimatePresence>
            {search && (
              <motion.div
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.15 }}
                onClick={() => { setSearch(''); setDebouncedSearch(''); }}
                style={{
                  position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                  cursor: 'pointer', padding: 2, display: 'flex', alignItems: 'center',
                }}
              >
                <X size={15} color={c.textTertiary} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.div>

      <div style={{ height: 20 }} />

      {/* Table */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2, ease: [0, 0, 0.2, 1] }}
        style={{
          flex: 1, background: c.surface, borderRadius: 12,
          border: `1px solid ${c.borderSubtle}`,
          overflow: 'hidden', display: 'flex', flexDirection: 'column',
        }}
      >
        {/* Loading */}
        {loading ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3, ease: [0, 0, 0.2, 1] }}
              style={{
                width: 32, height: 32, borderRadius: '50%',
                border: `3px solid ${c.primary}30`, borderTopColor: c.primary,
                animation: 'spin 1s linear infinite',
              }}
            />
          </div>
        ) : error ? (
          /* Error */
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
            <CloudOff size={48} color={c.warning} />
            <div style={{ fontSize: 16, fontWeight: 600, color: c.textPrimary }}>加载失败</div>
            <div style={{ fontSize: 12, color: c.textTertiary }}>{error}</div>
            <HoverPress>
              <motion.button
                whileTap={{ scale: 0.97 }}
                transition={spring}
                onClick={loadKeys}
                style={{
                  padding: '10px 20px', borderRadius: 8, border: 'none',
                  background: c.primary, color: c.onPrimary,
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >重试</motion.button>
            </HoverPress>
          </div>
        ) : filtered.length === 0 ? (
          /* Empty */
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
            <div style={{
              width: 72, height: 72, borderRadius: 16,
              background: c.surfaceLow, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <KeyRound size={36} color={c.textTertiary} />
            </div>
            <div style={{ fontSize: 16, fontWeight: 600, color: c.textSecondary }}>暂无密钥</div>
            <div style={{ fontSize: 13, color: c.textTertiary }}>从 JSON 文件导入密钥开始使用</div>
            <HoverPress>
              <motion.button
                whileTap={{ scale: 0.97 }}
                transition={spring}
                onClick={() => setImportOpen(true)}
                style={{
                  padding: '10px 20px', borderRadius: 8, border: 'none',
                  background: c.primary, color: c.onPrimary,
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}
              >
                <Upload size={18} />
                导入密钥
              </motion.button>
            </HoverPress>
          </div>
        ) : (
          /* Table */
          <>
            {/* Header row */}
            <div style={{
              height: 46, padding: '0 8px', background: c.surfaceLow,
              display: 'flex', alignItems: 'center',
              borderBottom: `1px solid ${c.borderSubtle}`,
            }}>
              <div style={{ flex: 3, paddingLeft: 8, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>密钥</div>
              <div style={{ flex: 2, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>服务商</div>
              <div style={{ flex: 1, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>状态</div>
              <div style={{ flex: 1, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5, textAlign: 'right' }}>延迟</div>
              <div style={{ flex: 1, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>模型</div>
              <div style={{ flex: 1, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>余额</div>
              <div style={{ flex: 1, fontSize: 11, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>操作</div>
            </div>

            {/* Rows */}
            <div style={{ flex: 1, overflow: 'auto' }}>
              {filtered.map((k, i) => {
                const ss = getStatusStyle(k.status);
                const isCopied = copiedKey === k.key_masked;
                const isChecking = checkingKey === k.key_masked;
                return (
                  <KeyRow
                    key={k.key_masked}
                    colors={c}
                    info={k}
                    providerName={providers.find(p => p.name === k.provider)?.display_name || k.provider}
                    index={i}
                    statusStyle={ss}
                    isCopied={isCopied}
                    isChecking={isChecking}
                    onCopyFullKey={() => copyFullKey(k.key_masked)}
                    onCheck={() => checkSingle(k.key_masked)}
                    onDelete={() => setConfirmDelete(k.key_masked)}
                  />
                );
              })}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                height: 44, padding: '0 16px',
                borderTop: `1px solid ${c.borderSubtle}`,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span style={{ fontSize: 12, color: c.textTertiary }}>共 {total} 个密钥</span>
                <div style={{ width: 16 }} />
                {PAGE_SIZES.map(size => (
                  <motion.div
                    key={size}
                    whileTap={{ scale: 0.95 }}
                    transition={spring}
                    onClick={() => { setPageSize(size); setPage(1); }}
                    style={{
                      padding: '4px 8px', borderRadius: 5, cursor: 'pointer',
                      background: pageSize === size ? `${c.primary}26` : 'transparent',
                      border: `1px solid ${pageSize === size ? `${c.primary}80` : c.borderSubtle}`,
                      fontSize: 11, fontWeight: pageSize === size ? 600 : 500,
                      color: pageSize === size ? c.primary : c.textTertiary,
                    }}
                  >{size}</motion.div>
                ))}
                <div style={{ flex: 1 }} />
                <PageBtn colors={c} icon={ChevronLeft} enabled={page > 1} onTap={() => setPage(p => p - 1)} />
                <span style={{ fontSize: 12, fontWeight: 600, color: c.textSecondary }}>{page} / {totalPages}</span>
                <PageBtn colors={c} icon={ChevronRight} enabled={page < totalPages} onTap={() => setPage(p => p + 1)} />
              </div>
            )}
          </>
        )}
      </motion.div>

      {/* Import dialog */}
      <ImportDialog
        colors={c}
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImportSuccess={(fileName, newCount, dupeCount) => {
          onImportSuccess?.(fileName, newCount, dupeCount);
          loadKeys();
        }}
      />

      {/* Delete single key confirm dialog */}
      <AnimatePresence>
        {confirmDelete !== null && (
          <ConfirmDialog
            colors={c}
            title="删除密钥"
            desc="确定要删除这个密钥吗？此操作不可恢复。"
            confirmLabel="删除"
            destructive
            onConfirm={() => doDeleteKey(confirmDelete)}
            onCancel={() => setConfirmDelete(null)}
          />
        )}
      </AnimatePresence>

      {/* Clear all keys confirm dialog */}
      <AnimatePresence>
        {confirmClearAll && (
          <ConfirmDialog
            colors={c}
            title="清空所有密钥"
            desc="确定要清空所有密钥吗？此操作不可恢复。"
            confirmLabel="清空"
            destructive
            onConfirm={doClearAll}
            onCancel={() => setConfirmClearAll(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── KeyRow ──────────────────────────────────────────────────────────────

function KeyRow({ colors: c, info, providerName, index, statusStyle, isCopied, isChecking, onCopyFullKey, onCheck, onDelete }: {
  colors: Colors; info: KeyInfo; providerName: string; index: number;
  statusStyle: { bg: string; fg: string; label: string };
  isCopied: boolean; isChecking: boolean; onCopyFullKey: () => void; onCheck: () => void; onDelete: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  const displayKey = info.key_masked;
  const displayName = providerName;
  const latencyMs = info.tests?.latency_ms;
  const balanceDisplay = info.balance != null ? `${info.balance}` : '-';
  const modelCount = info.models?.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.03, 0.6), ease: [0, 0, 0.2, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        height: 46, padding: '0 8px',
        background: hovered ? c.surfaceHover : 'transparent',
        display: 'flex', alignItems: 'center',
        borderBottom: `1px solid ${c.borderSubtle}`,
        transition: 'background 150ms ease',
      }}
    >
      {/* Key with tooltip */}
      <div style={{ flex: 3, paddingLeft: 8 }} title={info.key_masked}>
        <span style={{
          fontFamily: 'Consolas', fontSize: 11, color: c.textSecondary,
        }}>
          {displayKey}
        </span>
      </div>
      {/* Provider with displayName */}
      <div style={{ flex: 2, fontSize: 13, color: c.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {displayName}
      </div>
      {/* Status */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 4 }}>
        <span
          style={{
            display: 'inline-block', padding: '2px 8px', borderRadius: 6,
            fontSize: 11, fontWeight: 600, background: statusStyle.bg, color: statusStyle.fg,
          }}
          title={info.last_error ? `[${info.error_type || 'error'}] ${info.last_error}` : undefined}
        >{statusStyle.label}</span>
        {info.last_error && (
          <span title={`${info.error_type || 'error'}: ${info.last_error}`} style={{ display: 'flex', flexShrink: 0 }}>
            <AlertCircle size={13} color={c.warning} />
          </span>
        )}
      </div>
      {/* Latency */}
      <div style={{ flex: 1, textAlign: 'right', fontFamily: 'Consolas', fontSize: 11, color: c.textTertiary }}>
        {latencyMs != null ? `${latencyMs}ms` : '-'}
      </div>
      {/* Models */}
      <div style={{ flex: 1, fontSize: 13, color: c.textSecondary }}>
        {modelCount != null ? `${modelCount} 个` : '-'}
      </div>
      {/* Balance with currency */}
      <div style={{ flex: 1, fontSize: 13, color: c.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {balanceDisplay}
      </div>
      {/* Actions */}
      <div style={{ flex: 1, display: 'flex', gap: 4 }}>
        <motion.button
          whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
          transition={spring}
          onClick={onCopyFullKey}
          style={{
            width: 30, height: 30, borderRadius: 6, border: 'none',
            background: isCopied ? `${c.success}1F` : hovered ? `${c.primary}1F` : 'transparent',
            color: isCopied ? c.success : hovered ? c.primary : c.textTertiary,
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 150ms ease',
          }}
          title="复制完整密钥"
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={isCopied ? 'check' : 'copy'}
              initial={{ scale: 0.5, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0.5, rotate: 90 }}
              transition={{ type: 'spring', damping: 15, stiffness: 300 }}
            >
              {isCopied ? <Check size={16} /> : <Copy size={16} />}
            </motion.div>
          </AnimatePresence>
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
          transition={spring}
          onClick={onCheck}
          disabled={isChecking}
          style={{
            width: 30, height: 30, borderRadius: 6, border: 'none',
            background: hovered ? `${c.primary}1F` : 'transparent',
            color: hovered ? c.primary : c.textTertiary, cursor: isChecking ? 'wait' : 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 150ms ease',
          }}
          title="检测"
        >
          <motion.div
            animate={isChecking ? { rotate: 360 } : { rotate: 0 }}
            transition={isChecking ? { duration: 1, repeat: Infinity, ease: 'linear' } : { duration: 0.3 }}
          >
            <CheckCircle size={16} />
          </motion.div>
        </motion.button>
        <motion.button
          whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
          transition={spring}
          onClick={onDelete}
          style={{
            width: 30, height: 30, borderRadius: 6, border: 'none',
            background: hovered ? `${c.error}1F` : 'transparent',
            color: hovered ? c.error : c.textTertiary, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 150ms ease',
          }}
          title="删除"
        >
          <Trash2 size={16} />
        </motion.button>
      </div>
    </motion.div>
  );
}

// ─── FilterChip ──────────────────────────────────────────────────────────

function FilterChip({ colors: c, label, icon: Icon, selected, onTap }: {
  colors: Colors; label: string; icon: React.ElementType; selected: boolean; onTap: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      onClick={onTap}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: '9px 16px', borderRadius: 9, cursor: 'pointer',
        background: selected ? `${c.primary}26` : hovered ? c.surfaceHover : c.surfaceLow,
        border: `${selected ? 1.5 : 1}px solid ${selected ? `${c.primary}80` : hovered ? c.border : c.borderSubtle}`,
        fontSize: 13, fontWeight: 600,
        color: selected ? c.primary : c.textPrimary,
        display: 'flex', alignItems: 'center', gap: selected ? 7 : 0,
        boxShadow: (selected || hovered) ? `0 ${hovered ? 4 : 2}px ${hovered ? 12 : 8}px ${c.shadow}` : 'none',
        transition: 'background 200ms ease, border-color 200ms ease, box-shadow 200ms ease, gap 200ms ease',
      }}
    >
      <motion.div
        animate={{ width: selected ? 15 : 0, opacity: selected ? 1 : 0, scale: selected ? 1 : 0.3 }}
        transition={{ type: 'spring', damping: 14, stiffness: 280 }}
        style={{ overflow: 'hidden', display: 'flex', alignItems: 'center', flexShrink: 0 }}
      >
        <Icon size={15} />
      </motion.div>
      {label}
    </motion.div>
  );
}

// ─── ProviderDropdown ────────────────────────────────────────────────────

function ProviderDropdown({ colors: c, providers, value, onChange }: {
  colors: Colors; providers: ProviderInfo[]; value: string | null; onChange: (v: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const selected = providers.find(p => p.name === value);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <HoverPress>
        <motion.div
          onClick={() => setOpen(!open)}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          whileTap={{ scale: 0.97 }}
          transition={spring}
          style={{
            padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
            border: `1px solid ${hovered || open ? c.border : c.borderSubtle}`,
            background: hovered ? c.surfaceHover : c.surfaceLow,
            color: c.textPrimary, fontSize: 12, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 8, minWidth: 120,
            boxShadow: hovered ? `0 2px 8px ${c.shadow}` : 'none',
            transition: 'background 150ms ease, border-color 150ms ease, box-shadow 150ms ease',
          }}
        >
          {selected && <Cloud size={14} color={c.primary} />}
          {selected?.display_name || '所有服务商'}
          <motion.div
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
            <ChevronRight size={12} color={c.textTertiary} style={{ transform: 'rotate(90deg)' }} />
          </motion.div>
        </motion.div>
      </HoverPress>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ type: 'spring', damping: 22, stiffness: 350 }}
            style={{
              position: 'absolute', top: '100%', left: 0, right: 0,
              zIndex: 50, marginTop: 4,
              background: c.surface, borderRadius: 10,
              border: `1px solid ${c.borderSubtle}`,
              boxShadow: `0 8px 24px ${c.shadow}`,
              overflow: 'hidden', maxHeight: 240, overflowY: 'auto',
            }}
          >
            {/* "All providers" option */}
            <DropdownItem
              colors={c}
              label="所有服务商"
              selected={value === null}
              index={0}
              onClick={() => { onChange(null); setOpen(false); }}
            />

            {/* Divider */}
            <motion.div
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.05, duration: 0.2 }}
              style={{ height: 1, background: c.divider, margin: '2px 8px', transformOrigin: 'left' }}
            />

            {/* Provider items with stagger */}
            {providers.map((p, i) => (
              <DropdownItem
                key={p.name}
                colors={c}
                label={p.display_name}
                sublabel={p.name}
                selected={value === p.name}
                index={i + 1}
                onClick={() => { onChange(p.name); setOpen(false); }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DropdownItem({ colors: c, label, sublabel, selected, index, onClick }: {
  colors: Colors; label: string; sublabel?: string; selected: boolean; index: number; onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03, duration: 0.2, ease: [0, 0, 0.2, 1] }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: '8px 14px', cursor: 'pointer',
        color: selected ? c.primary : c.textSecondary,
        fontWeight: selected ? 600 : 400,
        background: selected ? `${c.primary}0D` : hovered ? c.surfaceHover : 'transparent',
        display: 'flex', alignItems: 'center', gap: 8,
        transition: 'background 120ms ease',
      }}
    >
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ scale: 0, rotate: -45 }}
            animate={{ scale: 1, rotate: 0 }}
            exit={{ scale: 0, rotate: 45 }}
            transition={{ type: 'spring', damping: 10, stiffness: 200 }}
          >
            <Check size={12} color={c.primary} />
          </motion.div>
        )}
      </AnimatePresence>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12 }}>{label}</div>
        {sublabel && <div style={{ fontSize: 10, color: c.textTertiary, marginTop: 1 }}>{sublabel}</div>}
      </div>
    </motion.div>
  );
}

// ─── PageBtn ─────────────────────────────────────────────────────────────

function PageBtn({ colors: c, icon: Icon, enabled, onTap }: {
  colors: Colors; icon: React.ElementType; enabled: boolean; onTap: () => void;
}) {
  return (
    <motion.div
      whileTap={enabled ? { scale: 0.9 } : undefined}
      transition={spring}
      onClick={enabled ? onTap : undefined}
      style={{
        width: 28, height: 28, borderRadius: 6,
        background: enabled ? c.surfaceLow : 'transparent',
        border: `1px solid ${enabled ? c.borderSubtle : 'transparent'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: enabled ? 'pointer' : 'default',
      }}
    >
      <Icon size={18} color={enabled ? c.textSecondary : `${c.textTertiary}4D`} />
    </motion.div>
  );
}
