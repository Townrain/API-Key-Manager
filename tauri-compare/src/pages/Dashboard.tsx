import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence, useAnimation } from 'framer-motion';
import {
  Key, CheckCircle, XCircle, Cloud, CloudOff,
  Upload, Shield, Rocket, Download, Trash2,
  TrendingUp, RefreshCw, ArrowRight, Loader2,
} from 'lucide-react';
import type { Colors } from '../theme/tokens';
import { api, type Stats } from '../api/client';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { UploadIcon, ShieldIcon, RocketIcon, DownloadIcon, TrashIcon } from '../components/AnimatedActionIcons';
import { ImportDialog } from '../components/ImportDialog';

const STAT_CONFIGS = [
  { key: 'total_keys' as const, label: '总密钥数', icon: Key, colorKey: 'info' as const },
  { key: 'valid_keys' as const, label: '有效', icon: CheckCircle, colorKey: 'success' as const },
  { key: 'invalid_keys' as const, label: '无效', icon: XCircle, colorKey: 'error' as const },
  { key: 'providers' as const, label: '服务商', icon: Cloud, colorKey: 'secondary' as const },
];

interface Props {
  colors: Colors;
  visible?: boolean;
  onNavigate?: (page: string) => void;
  onImportSuccess?: (fileName: string, newCount: number, dupeCount: number) => void;
}

export function Dashboard({ colors: c, visible, onNavigate: _onNavigate, onImportSuccess }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'warning' } | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Progress streaming state
  const [progress, setProgress] = useState<{ active: boolean; current: number; total: number; status: string; label: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    abortRef.current?.abort();
  }, []);

  const load = () => {
    setLoading(true);
    setError('');

    const tryConnect = (retries: number) => {
      api.getStats()
        .then(data => {
          setStats(data);
          setLoading(false);
        })
        .catch(e => {
          if (retries > 0) {
            setTimeout(() => tryConnect(retries - 1), 500);
          } else {
            setError(e.message);
            setLoading(false);
          }
        });
    };

    tryConnect(5); // 5 retries with 500ms delay = 2.5s total wait
  };

  // Silent refresh — no loading flash
  const refreshStats = useCallback(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => { load(); }, []);

  // Refresh when page becomes visible
  const prevVisible = useRef(false);
  useEffect(() => {
    if (visible && !prevVisible.current) {
      refreshStats();
    }
    prevVisible.current = visible ?? false;
  }, [visible, refreshStats]);

  // Auto-poll every 30s while visible
  useEffect(() => {
    if (!visible) return;
    const timer = setInterval(refreshStats, 30_000);
    return () => clearInterval(timer);
  }, [visible, refreshStats]);

  const showToast = (msg: string, type: 'success' | 'error' | 'warning' = 'success') => {
    setToast({ msg, type });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(null), type === 'error' ? 4000 : 2000);
  };

  const handleImport = () => setImportOpen(true);

  const startProgressStream = (label: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setProgress({ active: true, current: 0, total: 0, status: 'loading', label });

    api.progressStream(
      (event) => {
        if (event.type === 'progress' || event.data?.current != null) {
          setProgress(prev => prev ? {
            ...prev,
            current: event.data?.current ?? prev.current,
            total: event.data?.total ?? prev.total,
            status: event.data?.status ?? prev.status,
          } : null);
        }
        if (event.type === 'complete' || event.data?.status === 'done' || event.data?.status === 'error') {
          setProgress(prev => prev ? { ...prev, active: false, status: 'done' } : null);
          setTimeout(() => {
            setProgress(null);
            refreshStats();
          }, 1500);
        }
      },
      controller.signal,
    ).catch(() => {
      setProgress(null);
    });
  };

  const handleCheckAll = async () => {
    if (!stats || (stats.total ?? 0) === 0) {
      showToast('没有可供检测的密钥', 'warning');
      return;
    }
    try {
      await api.checkAll();
      showToast('检测已启动');
      startProgressStream('检测全部');
    } catch (e: any) {
      showToast('检测启动失败: ' + e.message, 'error');
    }
  };

  const handleTestAll = async () => {
    if (!stats || (stats.total ?? 0) === 0) {
      showToast('没有可供测试的密钥', 'warning');
      return;
    }
    try {
      await api.testToken();
      showToast('测试已启动');
      startProgressStream('测试全部');
    } catch (e: any) {
      showToast('测试启动失败: ' + e.message, 'error');
    }
  };

  const handleExport = async () => {
    try {
      const res = await api.exportKeys();
      if (!res.keys.length) {
        showToast('没有可导出的密钥', 'warning');
        return;
      }
      const blob = new Blob([JSON.stringify(res.keys, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'keys_export.json'; a.click();
      URL.revokeObjectURL(url);
      showToast(`已导出 ${res.keys.length} 个密钥`);
    } catch (e: any) {
      showToast('导出失败: ' + e.message, 'error');
    }
  };

  const handleClear = () => setConfirmClearOpen(true);
  const doClear = async () => {
    setConfirmClearOpen(false);
    try {
      await api.clearKeys();
      showToast('已清空所有密钥');
      load();
    } catch (e: any) {
      showToast('清空失败: ' + e.message, 'error');
    }
  };

  const vals = stats
    ? (() => {
        const provs = Object.values(stats.providers || {});
        const totalValid = provs.reduce((s, p) => s + (p.valid || 0), 0);
        const totalInvalid = provs.reduce((s, p) => s + (p.invalid || 0), 0);
        return [
          stats.total ?? provs.reduce((s, p) => s + (p.total || 0), 0),
          totalValid,
          totalInvalid,
          provs.length,
        ];
      })()
    : [0, 0, 0, 0];

  const quickActions = [
    { id: 'import', icon: Upload, label: '导入密钥', desc: '从 JSON 文件批量导入', color: c.info, onClick: handleImport, AnimatedIcon: UploadIcon },
    { id: 'checkAll', icon: Shield, label: '检测全部', desc: '验证所有密钥', color: c.primary, onClick: handleCheckAll, AnimatedIcon: ShieldIcon },
    { id: 'testAll', icon: Rocket, label: '测试全部', desc: 'Token与并发测试', color: c.warning, onClick: handleTestAll, AnimatedIcon: RocketIcon },
    { id: 'export', icon: Download, label: '导出有效密钥', desc: '导出可用密钥', color: c.success, onClick: handleExport, AnimatedIcon: DownloadIcon },
    { id: 'clear', icon: Trash2, label: '清空密钥', desc: '移除所有已导入密钥', color: c.error, onClick: handleClear, AnimatedIcon: TrashIcon },
  ];

  const toastIcon = toast?.type === 'error' ? '!' : toast?.type === 'warning' ? '!' : '✓';

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
            <h1 style={{ fontSize: 22, fontWeight: 700, color: c.textPrimary, margin: 0, letterSpacing: -0.5 }}>仪表盘</h1>
            <p style={{ fontSize: 13, color: c.textTertiary, margin: '4px 0 0' }}>概览与快捷操作</p>
          </div>
          <RefreshButton colors={c} onClick={load} />
        </div>
      </motion.div>

      <div style={{ height: 36 }} />

      {/* Error state */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0, 0, 0.2, 1] }}
          style={{
            width: '100%', padding: 20, marginBottom: 8,
            background: `${c.warning}0A`,
            borderRadius: 10,
            border: `1px solid ${c.warning}33`,
            display: 'flex', alignItems: 'center', gap: 14,
          }}
        >
          <CloudOff size={24} color={c.warning} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: c.textPrimary }}>后端服务未连接</div>
            <div style={{ fontSize: 12, color: c.textTertiary, marginTop: 2 }}>{error}</div>
          </div>
          <motion.button
            whileTap={{ scale: 0.9 }}
            transition={{ type: 'spring', damping: 8, stiffness: 250 }}
            onClick={load}
            style={{
              padding: '6px 14px', borderRadius: 6,
              border: 'none', background: `${c.warning}1A`,
              color: c.warning, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}
          >重试</motion.button>
        </motion.div>
      )}

      {/* Stat cards */}
      {!error && (
        <div style={{ display: 'flex', gap: 16 }}>
          {STAT_CONFIGS.map((cfg, i) => {
            const color = c[cfg.colorKey];
            return (
              <StatCard
                key={cfg.key}
                colors={c}
                title={cfg.label}
                value={loading ? '-' : String(vals[i])}
                icon={cfg.icon}
                color={color}
                index={i}
              />
            );
          })}
        </div>
      )}

      <div style={{ height: 56 }} />

      {/* Quick actions */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.24, ease: [0, 0, 0.2, 1] }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: c.textPrimary, letterSpacing: -0.2 }}>快捷操作</div>
      </motion.div>
      <div style={{ height: 20 }} />
      <div style={{ display: 'flex', gap: 12 }}>
        {quickActions.map((a, i) => (
          <QuickAction
            key={a.id}
            colors={c}
            icon={a.icon}
            label={a.label}
            description={a.desc}
            color={a.color}
            index={5 + i}
            onTap={a.onClick}
            AnimatedIcon={a.AnimatedIcon}
          />
        ))}
      </div>

      {/* Progress bar — shown during long-running operations */}
      <AnimatePresence>
        {progress && (
          <motion.div
            initial={{ opacity: 0, height: 0, marginTop: 0 }}
            animate={{ opacity: 1, height: 'auto', marginTop: 24 }}
            exit={{ opacity: 0, height: 0, marginTop: 0 }}
            transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              background: c.surface, borderRadius: 10,
              border: `1px solid ${c.borderSubtle}`,
              padding: '16px 20px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                <Loader2 size={16} color={c.primary} style={{ animation: progress.active ? 'spin 1s linear infinite' : 'none' }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary }}>{progress.label}</span>
                <span style={{ fontSize: 12, color: c.textTertiary }}>
                  {progress.total > 0 ? `${progress.current} / ${progress.total}` : '处理中...'}
                </span>
                <div style={{ flex: 1 }} />
                {!progress.active && (
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                    background: `${c.success}1F`, color: c.success,
                  }}>完成</span>
                )}
              </div>
              <div style={{ height: 6, borderRadius: 4, background: c.surfaceLow, overflow: 'hidden' }}>
                <motion.div
                  animate={{
                    width: progress.total > 0
                      ? `${(progress.current / progress.total) * 100}%`
                      : progress.active ? '100%' : '0%',
                  }}
                  transition={{ duration: 0.4, ease: 'easeOut' }}
                  style={{
                    height: '100%',
                    background: progress.active
                      ? `linear-gradient(90deg, ${c.primary}, ${c.info})`
                      : c.success,
                    borderRadius: 4,
                    ...(progress.active && progress.total === 0 ? {
                      animation: 'progress-indeterminate 1.5s ease-in-out infinite',
                    } : {}),
                  }}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Provider distribution — always rendered to prevent layout shift */}
      <div style={{ height: 56 }} />
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.48, ease: [0, 0, 0.2, 1] }}
        style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: c.textPrimary, letterSpacing: -0.2, marginBottom: 20 }}>服务商分布</div>
        <div style={{
          background: c.surface, borderRadius: 12, padding: '16px 20px',
          border: `1px solid ${c.borderSubtle}`,
          flex: 1, minHeight: 0, overflow: 'auto',
        }}>
          {!error && stats && typeof stats.providers === 'object' && stats.providers !== null && (() => {
            const entries = Object.entries(stats.providers as Record<string, { total: number; valid: number; invalid: number; display_name: string }>)
              .sort(([, a], [, b]) => b.total - a.total);
            const maxTotal = Math.max(...entries.map(([, v]) => v.total), 1);
            if (entries.length === 0) {
              return (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  justifyContent: 'center', padding: '40px 0', gap: 8,
                }}>
                  <Cloud size={32} color={`${c.textTertiary}80`} />
                  <div style={{ fontSize: 13, color: c.textTertiary }}>导入密钥后将显示服务商分布</div>
                </div>
              );
            }
            return entries.map(([name, info], i) => (
              <ProviderBar
                key={name}
                colors={c}
                name={info.display_name || name}
                total={info.total}
                valid={info.valid}
                invalid={info.invalid}
                maxTotal={maxTotal}
                index={i}
              />
            ));
          })()}
        </div>
      </motion.div>

      {/* Import dialog */}
      <ImportDialog
        colors={c}
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImportSuccess={(fileName, newCount, dupeCount) => {
          onImportSuccess?.(fileName, newCount, dupeCount);
          showToast(`导入成功: ${fileName}`);
          load();
        }}
      />

      {/* Confirm clear dialog */}
      <AnimatePresence>
        {confirmClearOpen && (
          <ConfirmDialog
            colors={c}
            title="确认清空"
            desc="确定要清空所有已导入的密钥吗？导入历史记录不会被删除。"
            destructive
            onConfirm={doClear}
            onCancel={() => setConfirmClearOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Toast — bottom full width */}
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
              background: toast.type === 'error' ? c.error : toast.type === 'warning' ? c.warning : c.success,
              color: '#fff', fontSize: 13, fontWeight: 600,
              boxShadow: `0 6px 16px ${toast.type === 'error' ? c.error : toast.type === 'warning' ? c.warning : c.success}59`,
              display: 'flex', alignItems: 'center', gap: 12,
            }}
          >
            <span style={{ fontSize: 16 }}>{toastIcon}</span>
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── RefreshButton (matches Flutter RefreshButton) ───────────────────────

function RefreshButton({ colors: c, onClick }: { colors: Colors; onClick: () => void }) {
  const [hovered, setHovered] = useState(false);
  const spinControls = useAnimation();

  const handleClick = useCallback(async () => {
    onClick();
    // 360° spin with elastic bounce (matches Flutter elasticOut 700ms)
    await spinControls.start({
      rotate: 360,
      transition: { duration: 0.7, ease: [0.68, -0.55, 0.265, 1.55] },
    });
    spinControls.set({ rotate: 0 });
  }, [onClick, spinControls]);

  return (
    <motion.div
      whileHover={{ y: 2 }}
      whileTap={{ scale: 0.9 }}
      transition={{ type: 'spring', damping: 8, stiffness: 250 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      style={{
        padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
        border: `1px solid ${hovered ? c.border : c.borderSubtle}`,
        background: hovered ? c.surfaceHover : 'transparent',
        display: 'flex', alignItems: 'center', gap: 6,
        boxShadow: hovered ? `0 3px 8px ${c.shadow}` : 'none',
        transition: 'background 150ms ease, border-color 150ms ease, box-shadow 150ms ease',
        fontSize: 13, fontWeight: 500, color: c.textSecondary,
      }}
    >
      <motion.div animate={spinControls}>
        <RefreshCw size={15} />
      </motion.div>
      <span>刷新</span>
    </motion.div>
  );
}

// ─── StatCard (matches Flutter StatCard with spring physics) ─────────────

function StatCard({ colors: c, title, value, icon: Icon, color, index }: {
  colors: Colors; title: string; value: string; icon: React.ElementType; color: string; index: number;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: 4 }}
      transition={{
        opacity: { duration: 0.4, delay: index * 0.06, ease: [0, 0, 0.2, 1] },
        y: { type: 'spring', damping: 10, stiffness: 250 },
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        flex: 1, padding: 20, borderRadius: 12,
        background: c.surface,
        border: `1px solid ${hovered ? `${color}59` : c.borderSubtle}`,
        boxShadow: hovered ? `0 6px 20px ${color}1F` : 'none',
        transition: 'border 250ms cubic-bezier(0.25,0.46,0.45,0.94), box-shadow 250ms cubic-bezier(0.25,0.46,0.45,0.94), background 250ms cubic-bezier(0.25,0.46,0.45,0.94)',
        cursor: 'default',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `${color}${hovered ? '33' : '1A'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'background 250ms ease',
        }}>
          <Icon size={20} color={color} />
        </div>
        <div style={{ flex: 1 }} />
        <motion.div
          initial={false}
          animate={{ rotate: hovered ? 25 : 0, opacity: hovered ? 0.7 : 0.3 }}
          transition={{ type: 'spring', damping: 8, stiffness: 180 }}
        >
          <TrendingUp size={16} color={color} />
        </motion.div>
      </div>
      <div style={{ height: 16 }} />
      <motion.div
        initial={false}
        animate={{ fontSize: hovered ? 31 : 28 }}
        transition={{ type: 'spring', damping: 10, stiffness: 200 }}
        style={{
          fontWeight: 700, color, letterSpacing: -1, lineHeight: 1.1,
          fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
        }}
      >
        {value}
      </motion.div>
      <div style={{ height: 4 }} />
      <div style={{ fontSize: 12, fontWeight: 500, color: c.textTertiary, letterSpacing: 0.3 }}>{title}</div>
    </motion.div>
  );
}

// ─── QuickAction (matches Flutter _QuickAction with spring physics) ──────

function QuickAction({ colors: c, icon: Icon, label, description, color, isDestructive = false, index, onTap, AnimatedIcon }: {
  colors: Colors; icon: React.ElementType; label: string; description: string;
  color: string; isDestructive?: boolean; index: number; onTap: () => void;
  AnimatedIcon?: React.ComponentType<{ color: string; hovered: boolean }>;
}) {
  const [hovered, setHovered] = useState(false);
  const [executing, setExecuting] = useState(false);

  const handleTap = async () => {
    if (executing) return;
    setExecuting(true);
    try {
      await onTap();
    } finally {
      setExecuting(false);
    }
  };

  const accent = isDestructive ? c.error : color;
  const accentGlow = `${accent}1A`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: 4 }}
      whileTap={{ scale: 0.93 }}
      transition={{
        opacity: { duration: 0.4, delay: index * 0.06, ease: [0, 0, 0.2, 1] },
        y: { type: 'spring', damping: 10, stiffness: 250 },
        scale: { type: 'spring', damping: 10, stiffness: 250 },
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleTap}
      style={{
        flex: 1, padding: 16, borderRadius: 10, cursor: 'pointer',
        background: hovered ? c.surfaceHover : c.surface,
        border: `1px solid ${hovered ? `${accent}40` : c.borderSubtle}`,
        boxShadow: hovered ? `0 6px 18px ${c.shadow}` : 'none',
        transition: 'border 250ms cubic-bezier(0.25,0.46,0.45,0.94), box-shadow 250ms cubic-bezier(0.25,0.46,0.45,0.94), background 250ms cubic-bezier(0.25,0.46,0.45,0.94)',
        display: 'flex', alignItems: 'center', gap: 14,
      }}
    >
      <div style={{
        width: 40, height: 40, borderRadius: 8,
        background: hovered ? `${accent}2E` : accentGlow,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'background 250ms ease',
        flexShrink: 0,
      }}>
        {executing ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            style={{ width: 18, height: 18, border: `2px solid ${accent}30`, borderTopColor: accent, borderRadius: '50%' }}
          />
        ) : AnimatedIcon ? (
          <AnimatedIcon color={accent} hovered={hovered} />
        ) : (
          <Icon size={18} color={accent} />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary }}>{label}</div>
        <div style={{ fontSize: 11, color: c.textTertiary, marginTop: 2 }}>{description}</div>
      </div>
      <motion.div
        animate={{ rotate: hovered ? 0 : -45, x: hovered ? 3 : 0 }}
        transition={{ type: 'spring', damping: 10, stiffness: 200 }}
      >
        {executing ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            style={{ width: 14, height: 14, border: `2px solid ${accent}30`, borderTopColor: accent, borderRadius: '50%' }}
          />
        ) : (
          <ArrowRight size={12} color={hovered ? accent : c.textTertiary} />
        )}
      </motion.div>
    </motion.div>
  );
}

// ─── ProviderBar (horizontal distribution bar) ───────────────────────────

function ProviderBar({ colors: c, name, total, valid, invalid, maxTotal, index }: {
  colors: Colors; name: string; total: number; valid: number; invalid: number; maxTotal: number; index: number;
}) {
  const [hovered, setHovered] = useState(false);
  const pct = (total / maxTotal) * 100;
  const validPct = total > 0 ? (valid / total) * 100 : 0;
  const invalidPct = total > 0 ? (invalid / total) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: 0.5 + index * 0.04, ease: [0, 0, 0.2, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '8px 0',
        borderBottom: index > 0 ? `1px solid ${c.borderSubtle}` : 'none',
      }}
    >
      <div style={{
        width: 120, fontSize: 13, fontWeight: 500, color: c.textPrimary,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0,
      }}>
        {name}
      </div>
      <div style={{ flex: 1, height: 20, position: 'relative' }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, delay: 0.6 + index * 0.04, ease: [0, 0, 0.2, 1] }}
          style={{
            height: '100%', borderRadius: 4, overflow: 'hidden',
            background: `${c.primary}1A`,
            display: 'flex',
          }}
        >
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${validPct}%` }}
            transition={{ duration: 0.5, delay: 0.8 + index * 0.04, ease: [0, 0, 0.2, 1] }}
            style={{ background: `${c.success}88`, borderRadius: '4px 0 0 4px' }}
          />
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${invalidPct}%` }}
            transition={{ duration: 0.5, delay: 0.9 + index * 0.04, ease: [0, 0, 0.2, 1] }}
            style={{ background: `${c.error}66` }}
          />
        </motion.div>
      </div>
      <motion.span
        animate={{ color: hovered ? c.textPrimary : c.textTertiary }}
        style={{
          width: 36, textAlign: 'right', fontSize: 12, fontWeight: 600,
          fontVariantNumeric: 'tabular-nums', flexShrink: 0,
        }}
      >
        {total}
      </motion.span>
    </motion.div>
  );
}
