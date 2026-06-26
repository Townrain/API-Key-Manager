import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RefreshCw, FileText, Globe, Trash2, X, Calendar, ChevronRight } from 'lucide-react';
import type { Colors } from '../theme/tokens';
import { curves } from '../theme/tokens';
import { HoverPress, BouncyPress, StaggeredFadeIn } from '../theme/animations';
import { api, type OperationEntry, type ProxyStatus } from '../api/client';
import { ConfirmDialog } from '../components/ConfirmDialog';

const bouncyOut = curves.bouncyOut;

interface Props { colors: Colors; visible?: boolean }

export function LogsPage({ colors: c, visible }: Props) {
  const [operations, setOperations] = useState<OperationEntry[]>([]);
  const [proxy, setProxy] = useState<ProxyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [proxyLoading, setProxyLoading] = useState(true);
  const [spins, setSpins] = useState(0);
  const [confirmClear, setConfirmClear] = useState(false);

  // Filter state
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [timeFrom, setTimeFrom] = useState('');
  const [timeTo, setTimeTo] = useState('');
  const [showFilter, setShowFilter] = useState(false);

  const load = useCallback(() => {
    setSpins(s => s + 1);
    Promise.all([
      api.getOperations().then(setOperations),
      api.getProxy().then(setProxy).finally(() => setProxyLoading(false)),
    ]).finally(() => {
      setLoading(false);
    });
  }, []);

  useEffect(() => { load(); }, []);

  // Refresh data when page becomes visible
  const prevVis = useRef(false);
  useEffect(() => {
    if (visible && !prevVis.current) {
      load();
    }
    prevVis.current = visible ?? false;
  }, [visible, load]);

  const handleClearAll = async () => {
    try {
      // If a date filter is active, pass the dateFrom to only clear that day's logs
      await api.clearLogs(dateFrom || undefined);
      if (dateFrom) {
        // Remove cleared operations from local state
        setOperations(prev => prev.filter(op => {
          if (!op.timestamp) return true;
          return op.timestamp.slice(0, 10) !== dateFrom;
        }));
      } else {
        setOperations([]);
      }
    } catch (e) {
      console.error('Clear logs failed:', e);
    }
    setConfirmClear(false);
  };

  // Filtered operations (newest first)
  const filtered = useMemo(() => {
    return operations
      .filter(op => {
        if (!op.timestamp) return true;
        const ts = op.timestamp;
        const datePart = ts.slice(0, 10);
        const timePart = ts.length > 11 ? ts.slice(11, 19) : '';
        if (dateFrom && datePart < dateFrom) return false;
        if (dateTo && datePart > dateTo) return false;
        if (timeFrom && timePart < timeFrom) return false;
        if (timeTo && timePart > timeTo) return false;
        return true;
      })
      .sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
  }, [operations, dateFrom, dateTo, timeFrom, timeTo]);

  const hasFilter = dateFrom || dateTo || timeFrom || timeTo;
  const clearFilter = () => { setDateFrom(''); setDateTo(''); setTimeFrom(''); setTimeTo(''); };

  // Auto-show filter panel when filters are active
  useEffect(() => {
    if (hasFilter) setShowFilter(true);
  }, [hasFilter]);

  return (
    <div style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <StaggeredFadeIn index={0}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: c.textPrimary, letterSpacing: -0.5, margin: 0 }}>日志</h1>
            <p style={{ fontSize: 13, color: c.textTertiary, margin: '4px 0 0' }}>操作日志与系统状态</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {operations.length > 0 && (
              <HoverPress pressDepth={2}>
                <BouncyPress onClick={() => setConfirmClear(true)}>
                  <div
                    style={{
                      padding: '6px 12px', borderRadius: 8, cursor: 'pointer',
                      border: `1px solid ${c.error}33`,
                      background: `${c.error}14`, color: c.error,
                      fontSize: 12, fontWeight: 600,
                      display: 'flex', alignItems: 'center', gap: 6,
                      transition: `background ${150}ms ease-out`,
                    }}
                  >
                    <Trash2 size={14} />
                    清空日志
                  </div>
                </BouncyPress>
              </HoverPress>
            )}
            <HoverPress pressDepth={2}>
              <BouncyPress onClick={load}>
                <div
                  style={{
                    padding: 8, borderRadius: 8, cursor: 'pointer',
                    border: `1px solid ${c.borderSubtle}`,
                    background: 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: `background ${150}ms ease-out, border-color ${150}ms ease-out`,
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
                    transition={{ duration: 0.6, ease: bouncyOut }}
                  >
                    <RefreshCw size={18} color={c.textSecondary} />
                  </motion.div>
                </div>
              </BouncyPress>
            </HoverPress>
          </div>
        </div>
      </StaggeredFadeIn>

      {/* Proxy Status Card */}
      <StaggeredFadeIn index={1} style={{ marginTop: 24 }}>
        <div
          style={{
            background: c.surface, borderRadius: 10,
            border: `1px solid ${c.borderSubtle}`,
            padding: '12px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6,
              background: c.primaryGlow,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Globe size={16} color={c.primary} />
            </div>
            {proxyLoading ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <motion.div
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3 }}
                  style={{
                    width: 14, height: 14, borderRadius: '50%',
                    border: `2px solid ${c.textTertiary}40`, borderTopColor: c.textTertiary,
                    animation: 'spin 1s linear infinite',
                  }}
                />
                <span style={{ fontSize: 13, color: c.textTertiary }}>加载中...</span>
              </div>
            ) : proxy?.proxy ? (
              <>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: c.success,
                  boxShadow: `0 0 6px ${c.success}66`,
                }} />
                <span style={{
                  fontFamily: 'Consolas', fontSize: 13, color: c.textPrimary,
                  flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>{proxy.proxy}</span>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                  background: `${c.info}1F`, color: c.info,
                }}>{proxy.source === 'config' ? '配置文件' : '系统代理'}</span>
              </>
            ) : (
              <>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: c.textTertiary,
                }} />
                <span style={{ fontSize: 13, color: c.textSecondary }}>未配置代理</span>
                <span style={{
                  fontSize: 11, color: c.textTertiary, marginLeft: 'auto',
                }}>所有请求直连</span>
              </>
            )}
          </div>
          {/* Description */}
          <div style={{
            fontSize: 11, color: c.textTertiary, marginTop: 8, paddingLeft: 40,
          }}>
            {proxy?.proxy
              ? '代理用于转发密钥检测、余额查询等 API 请求'
              : '如需通过代理访问 API，请在 config.yaml 中配置 proxy 字段'}
          </div>
        </div>
      </StaggeredFadeIn>

      {/* Operations Log Header + Filter */}
      <StaggeredFadeIn index={2} style={{ marginTop: 16, marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: c.primaryGlow,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <FileText size={16} color={c.primary} />
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: c.textPrimary }}>操作日志</span>
          <span style={{
            fontSize: 11, fontWeight: 600, color: c.textTertiary,
            background: c.surfaceLow, padding: '2px 8px', borderRadius: 10,
          }}>{hasFilter ? `${filtered.length} / ${operations.length}` : `${operations.length}`} 条记录</span>
          <div style={{ flex: 1 }} />
          {/* Filter toggle button */}
          <HoverPress>
            <BouncyPress onClick={() => setShowFilter(v => !v)}>
              <div
                style={{
                  padding: '6px 12px', borderRadius: 8, cursor: 'pointer',
                  border: `1px solid ${showFilter || hasFilter ? `${c.primary}60` : c.borderSubtle}`,
                  background: showFilter || hasFilter ? `${c.primary}14` : 'transparent',
                  color: showFilter || hasFilter ? c.primary : c.textSecondary,
                  fontSize: 12, fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 6,
                  transition: 'all 150ms ease',
                }}
              >
                <Calendar size={14} />
                筛选
                {hasFilter && (
                  <span style={{
                    width: 16, height: 16, borderRadius: '50%',
                    background: c.primary, color: '#fff',
                    fontSize: 10, fontWeight: 700,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {(dateFrom ? 1 : 0) + (dateTo ? 1 : 0) + (timeFrom ? 1 : 0) + (timeTo ? 1 : 0)}
                  </span>
                )}
              </div>
            </BouncyPress>
          </HoverPress>
        </div>

        {/* Collapsible filter panel */}
        <AnimatePresence>
          {showFilter && (
            <motion.div
              initial={{ height: 0, opacity: 0, marginTop: 0 }}
              animate={{ height: 'auto', opacity: 1, marginTop: 12 }}
              exit={{ height: 0, opacity: 0, marginTop: 0 }}
              transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
              style={{ overflow: 'hidden' }}
            >
              <div style={{
                background: c.surface, borderRadius: 10,
                border: `1px solid ${c.borderSubtle}`,
                padding: '14px 16px',
                display: 'flex', flexDirection: 'column', gap: 10,
              }}>
                {/* From row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 600, color: c.textTertiary,
                    width: 28, textAlign: 'right', flexShrink: 0,
                  }}>从</span>
                  <DatePicker colors={c} value={dateFrom} onChange={setDateFrom} />
                  <TimePicker colors={c} value={timeFrom} onChange={setTimeFrom} />
                </div>
                {/* To row */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 600, color: c.textTertiary,
                    width: 28, textAlign: 'right', flexShrink: 0,
                  }}>至</span>
                  <DatePicker colors={c} value={dateTo} onChange={setDateTo} />
                  <TimePicker colors={c} value={timeTo} onChange={setTimeTo} />
                </div>
                {/* Actions */}
                {hasFilter && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 2, borderTop: `1px solid ${c.borderSubtle}` }}>
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                      onClick={clearFilter}
                      style={{
                        padding: '6px 14px', borderRadius: 6, cursor: 'pointer',
                        border: 'none', background: `${c.error}14`, color: c.error,
                        fontSize: 12, fontWeight: 600,
                        display: 'flex', alignItems: 'center', gap: 4,
                      }}
                    >
                      <X size={12} />
                      清除筛选
                    </motion.button>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </StaggeredFadeIn>

      {/* Operations Table */}
      <StaggeredFadeIn index={3} style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div
          style={{
            flex: 1, background: c.surface, borderRadius: 10,
            border: `1px solid ${c.borderSubtle}`,
            overflow: 'hidden', display: 'flex', flexDirection: 'column',
          }}
        >
          {/* Table Header */}
          <div style={{
            height: 40, padding: '0 16px',
            background: c.surfaceLow,
            display: 'flex', alignItems: 'center',
            borderBottom: `1px solid ${c.borderSubtle}`,
          }}>
            <span style={{ flex: 2, fontSize: 11, fontWeight: 600, color: c.textTertiary }}>时间</span>
            <span style={{ flex: 2, fontSize: 11, fontWeight: 600, color: c.textTertiary }}>操作</span>
            <span style={{ flex: 4, fontSize: 11, fontWeight: 600, color: c.textTertiary }}>详情</span>
            <span style={{ width: 36 }} />
          </div>

          {/* Table Body */}
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
            ) : filtered.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                style={{
                  padding: 60, textAlign: 'center',
                  color: c.textTertiary, fontSize: 13,
                }}
              >
                <FileText size={48} style={{ margin: '0 auto 16px', opacity: 0.4 }} />
                <div>{hasFilter ? '当前筛选条件下无日志' : '暂无操作日志'}</div>
              </motion.div>
            ) : (
              filtered.map((op, i) => (
                <OperationRow
                  key={op.timestamp || i}
                  colors={c}
                  entry={op}
                  index={i}
                />
              ))
            )}
          </div>
        </div>
      </StaggeredFadeIn>

      {/* Confirm Clear Dialog */}
      <AnimatePresence>
        {confirmClear && (
          <ConfirmDialog
            colors={c}
            title="清空日志"
            desc={dateFrom
              ? `确定要清空 ${dateFrom} 的操作日志吗？此操作不可恢复。`
              : "确定要清空所有操作日志吗？此操作不可恢复。"
            }
            confirmLabel="清空"
            destructive
            onConfirm={handleClearAll}
            onCancel={() => setConfirmClear(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── OperationRow ──────────────────────────────────────────────────────────

function OperationRow({ colors: c, entry, index }: {
  colors: Colors; entry: OperationEntry; index: number;
}) {
  const [hovered, setHovered] = useState(false);

  const actionColor = (action: string): string => {
    const a = action.toLowerCase();
    if (a.includes('import')) return c.info;
    if (a.includes('check')) return c.success;
    if (a.includes('test')) return c.warning;
    if (a.includes('delete') || a.includes('clear')) return c.error;
    return c.primary;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.03, 0.6) }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        height: 40, padding: '0 16px',
        display: 'flex', alignItems: 'center',
        borderBottom: `1px solid ${c.borderSubtle}`,
        cursor: 'default',
        background: hovered ? c.surfaceHover : 'transparent',
        transition: 'background 150ms ease',
      }}
    >
      <span style={{
        flex: 2, fontFamily: 'Consolas', fontSize: 11, color: c.textTertiary,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {entry.timestamp || '-'}
      </span>
      <span style={{ flex: 2 }}>
        <span style={{
          display: 'inline-block', padding: '2px 6px', borderRadius: 4,
          fontSize: 11, fontWeight: 600,
          background: `${actionColor(entry.action)}1F`,
          color: actionColor(entry.action),
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>{entry.action}</span>
      </span>
      <span style={{
        flex: 4, fontSize: 13, color: c.textSecondary,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>{entry.detail}</span>
    </motion.div>
  );
}

// ─── Custom dropdown select ────────────────────────────────────────────────

const pad = (n: number) => String(n).padStart(2, '0');

function CustomSelect({ colors: c, value, options, placeholder, flex, onChange }: {
  colors: Colors; value: string; options: { value: string; label: string }[];
  placeholder: string; flex?: number; onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const selected = options.find(o => o.value === value);

  const updatePos = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
  };

  const toggleOpen = () => {
    if (!open) updatePos();
    setOpen(o => !o);
  };

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (triggerRef.current && !triggerRef.current.contains(e.target as Node)) setOpen(false);
    };
    const scrollHandler = () => updatePos();
    document.addEventListener('mousedown', handler);
    window.addEventListener('scroll', scrollHandler, true);
    return () => {
      document.removeEventListener('mousedown', handler);
      window.removeEventListener('scroll', scrollHandler, true);
    };
  }, [open]);

  // Scroll selected into view when opening
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open && listRef.current) {
      const sel = listRef.current.querySelector('[data-selected="true"]');
      sel?.scrollIntoView({ block: 'nearest' });
    }
  }, [open]);

  return (
    <div ref={triggerRef} style={{ flex: flex ?? 1 }}>
      <div
        onClick={toggleOpen}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          padding: '6px 10px', borderRadius: 8, cursor: 'pointer',
          border: `1px solid ${open ? `${c.primary}80` : hovered ? c.border : c.borderSubtle}`,
          background: open ? `${c.primary}08` : hovered ? c.surfaceHover : c.surfaceLow,
          fontSize: 12, fontFamily: 'Consolas',
          color: selected ? c.textPrimary : c.textTertiary,
          boxShadow: open ? `0 0 0 2px ${c.primary}20` : 'none',
          transition: 'all 150ms ease',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 4,
          userSelect: 'none',
        }}
      >
        <span>{selected?.label || placeholder}</span>
        <motion.div
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          style={{ display: 'flex', flexShrink: 0 }}
        >
          <ChevronRight size={12} color={c.textTertiary} style={{ transform: 'rotate(90deg)' }} />
        </motion.div>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            ref={listRef}
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
            style={{
              position: 'fixed', top: pos.top, left: pos.left, width: pos.width,
              zIndex: 9999,
              background: c.surface, borderRadius: 10,
              border: `1px solid ${c.borderSubtle}`,
              boxShadow: `0 8px 24px ${c.shadow}`,
              overflow: 'hidden',
              maxHeight: 220,
            }}
          >
            <div style={{ overflowY: 'auto', maxHeight: 220, padding: '4px 0' }}>
              {options.map((opt) => {
                const isSel = opt.value === value;
                return (
                  <div
                    key={opt.value}
                    data-selected={isSel}
                    onClick={() => { onChange(opt.value); setOpen(false); }}
                    style={{
                      padding: '6px 10px', cursor: 'pointer',
                      fontSize: 12, fontFamily: 'Consolas',
                      color: isSel ? c.primary : c.textSecondary,
                      background: isSel ? `${c.primary}14` : 'transparent',
                      fontWeight: isSel ? 600 : 400,
                      transition: 'background 100ms ease',
                    }}
                    onMouseEnter={e => {
                      if (!isSel) e.currentTarget.style.background = c.surfaceHover;
                    }}
                    onMouseLeave={e => {
                      if (!isSel) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    {opt.label}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DatePicker({ colors: c, value, onChange }: {
  colors: Colors; value: string; onChange: (v: string) => void;
}) {
  const parts = value.split('-');
  const year = parts[0] || '';
  const month = parts[1] || '';
  const day = parts[2] || '';

  const set = (y: string, m: string, d: string) => {
    if (y && m && d) onChange(`${y}-${m}-${d}`);
    else if (y || m || d) onChange(`${y || '0000'}-${m || '01'}-${d || '01'}`);
    else onChange('');
  };

  const currentYear = new Date().getFullYear();
  const yearOpts = Array.from({ length: 11 }, (_, i) => {
    const v = String(currentYear - 5 + i);
    return { value: v, label: v };
  });
  const monthOpts = Array.from({ length: 12 }, (_, i) => {
    const v = pad(i + 1);
    return { value: v, label: v };
  });
  const daysInMonth = year && month ? new Date(Number(year), Number(month), 0).getDate() : 31;
  const dayOpts = Array.from({ length: daysInMonth }, (_, i) => {
    const v = pad(i + 1);
    return { value: v, label: v };
  });

  return (
    <div style={{ flex: 1, display: 'flex', gap: 4 }}>
      <CustomSelect colors={c} value={year} options={yearOpts} placeholder="年" flex={1.3}
        onChange={v => set(v, month, day)} />
      <CustomSelect colors={c} value={month} options={monthOpts} placeholder="月" flex={0.8}
        onChange={v => set(year, v, day)} />
      <CustomSelect colors={c} value={day} options={dayOpts} placeholder="日" flex={0.8}
        onChange={v => set(year, month, v)} />
    </div>
  );
}

function TimePicker({ colors: c, value, onChange }: {
  colors: Colors; value: string; onChange: (v: string) => void;
}) {
  const parts = value.split(':');
  const hour = parts[0] || '';
  const minute = parts[1] || '';
  const second = parts[2] || '';

  const set = (h: string, m: string, s: string) => {
    if (h || m || s) onChange(`${h || '00'}:${m || '00'}:${s || '00'}`);
    else onChange('');
  };

  const hourOpts = Array.from({ length: 24 }, (_, i) => ({ value: pad(i), label: pad(i) }));
  const minOpts = Array.from({ length: 60 }, (_, i) => ({ value: pad(i), label: pad(i) }));
  const secOpts = Array.from({ length: 60 }, (_, i) => ({ value: pad(i), label: pad(i) }));

  return (
    <div style={{ flex: 1, display: 'flex', gap: 4 }}>
      <CustomSelect colors={c} value={hour} options={hourOpts} placeholder="时"
        onChange={v => set(v, minute, second)} />
      <CustomSelect colors={c} value={minute} options={minOpts} placeholder="分"
        onChange={v => set(hour, v, second)} />
      <CustomSelect colors={c} value={second} options={secOpts} placeholder="秒"
        onChange={v => set(hour, minute, v)} />
    </div>
  );
}
