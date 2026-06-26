import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wallet, Plus, Trash2, Webhook, KeyRound, Pencil, History,
  ChevronDown, Check, X as XIcon, ShieldCheck, ListChecks, Bot, Wrench,
  AlertCircle, CheckCircle, XCircle, Loader2,
} from 'lucide-react';
import type { Colors } from '../theme/tokens';
import {
  api, type ProviderInfo, type CheckResult, type CheckBatchResponse,
  type TestSingleResponse, type BalanceResponse, type ModelsResponse,
  type WebhookInfo, type ModelTestResult, type SignatureReport,
} from '../api/client';

interface Props { colors: Colors; visible?: boolean }

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

export function ToolsPage({ colors: c, visible }: Props) {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [toasts, setToasts] = useState<ToastData[]>([]);
  useEffect(() => { api.getProviders().then(setProviders).catch(() => {}); }, []);

  // Refresh providers when page becomes visible
  const prevVisible = useRef(false);
  useEffect(() => {
    if (visible && !prevVisible.current) {
      api.getProviders().then(setProviders).catch(() => {});
    }
    prevVisible.current = visible ?? false;
  }, [visible]);

  const toastTimersRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  useEffect(() => () => { toastTimersRef.current.forEach(clearTimeout); toastTimersRef.current.clear(); }, []);

  const addToast = (type: 'success' | 'error', message: string, detail?: string) => {
    const id = ++toastId;
    setToasts(prev => [...prev, { id, type, message, detail }]);
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      toastTimersRef.current.delete(timer);
    }, type === 'success' ? 3000 : 5000);
    toastTimersRef.current.add(timer);
  };
  const dismissToast = (id: number) => setToasts(prev => prev.filter(t => t.id !== id));

  return (
    <div style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} colors={c} />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0, 0, 0.2, 1] }}
      >
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: c.textPrimary, letterSpacing: -0.5, margin: 0 }}>工具箱</h1>
          <p style={{ fontSize: 13, color: c.textTertiary, margin: '4px 0 0' }}>单键检测、批量检测、模型查询、测试工具</p>
        </div>
      </motion.div>

      <div style={{ flex: 1, overflow: 'auto', marginTop: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 900, paddingBottom: 24 }}>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.05, ease: [0, 0, 0.2, 1] }}>
            <ManualCheckPanel colors={c} providers={providers} />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.1, ease: [0, 0, 0.2, 1] }}>
            <BatchCheckPanel colors={c} addToast={addToast} />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.15, ease: [0, 0, 0.2, 1] }}>
            <ModelsPanel colors={c} providers={providers} addToast={addToast} />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.2, ease: [0, 0, 0.2, 1] }}>
            <SingleKeyToolsPanel colors={c} providers={providers} addToast={addToast} />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.25, ease: [0, 0, 0.2, 1] }}>
            <ModelTestPanel colors={c} providers={providers} addToast={addToast} />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.3, ease: [0, 0, 0.2, 1] }}>
            <SignatureReportPanel colors={c} addToast={addToast} />
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.35, ease: [0, 0, 0.2, 1] }}>
            <WebhookPanel colors={c} addToast={addToast} />
          </motion.div>
        </div>
      </div>
    </div>
  );
}

// ─── Panel Wrapper ──────────────────────────────────────────────────────

function Panel({ colors: c, icon, title, children }: {
  colors: Colors; icon: React.ReactNode; title: string; children: React.ReactNode;
}) {
  return (
    <div style={{
      background: c.surface, borderRadius: 10,
      border: `1px solid ${c.borderSubtle}`,
      padding: 20, width: '100%',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6,
          background: c.primaryGlow,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: c.primary,
        }}>{icon}</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: c.textPrimary }}>{title}</div>
      </div>
      {children}
    </div>
  );
}

// ─── Input with focus ring + optional prefix icon ──────────────────────

function Input({ colors: c, value, onChange, placeholder, prefixIcon, mono, type, disabled, style: extraStyle }: {
  colors: Colors; value: string; onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string; prefixIcon?: React.ReactNode; mono?: boolean; type?: string; disabled?: boolean; style?: React.CSSProperties;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{ position: 'relative', width: '100%', ...extraStyle }}>
      {prefixIcon && (
        <div style={{
          position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
          display: 'flex', alignItems: 'center', pointerEvents: 'none', color: focused ? c.primary : c.textTertiary,
          transition: 'color 200ms ease',
        }}>
          {prefixIcon}
        </div>
      )}
      <input
        type={type}
        disabled={disabled}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          width: '100%',
          padding: prefixIcon ? '8px 14px 8px 36px' : '8px 14px',
          borderRadius: 8,
          border: `1.5px solid ${focused ? c.primary : c.borderSubtle}`,
          background: c.surfaceLow,
          color: c.textPrimary, fontSize: 13, outline: 'none',
          fontFamily: mono ? 'Consolas' : 'inherit',
          transition: 'border-color 200ms ease',
          boxShadow: focused ? `0 0 0 3px ${c.primary}1A` : 'none',
        }}
      />
    </div>
  );
}

// ─── Textarea with focus ring ───────────────────────────────────────────

function Textarea({ colors: c, value, onChange, placeholder, rows = 4, ...rest }: {
  colors: Colors; value: string; onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  placeholder?: string; rows?: number; [key: string]: any;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <textarea
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      rows={rows}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      style={{
        width: '100%', padding: '8px 14px', borderRadius: 8,
        border: `1.5px solid ${focused ? c.primary : c.borderSubtle}`,
        background: c.surfaceLow,
        color: c.textPrimary, fontSize: 13, outline: 'none',
        fontFamily: 'Consolas', resize: 'vertical' as const,
        transition: 'border-color 200ms ease',
        boxShadow: focused ? `0 0 0 3px ${c.primary}1A` : 'none',
      }}
      {...rest}
    />
  );
}

// ─── Styled Button ─────────────────────────────────────────────────────

function Btn({ colors: c, label, loadingLabel, loading, disabled, variant = 'primary', onClick, icon }: {
  colors: Colors; label: string; loadingLabel?: string; loading?: boolean; disabled?: boolean;
  variant?: 'primary' | 'info'; onClick: () => void; icon?: React.ReactNode;
}) {
  const bg = variant === 'info' ? c.info : c.primary;
  const [hovered, setHovered] = useState(false);
  return (
    <HoverPress>
      <motion.button
        whileTap={{ scale: 0.97 }}
        transition={spring}
        onClick={onClick}
        disabled={disabled || loading}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          padding: '10px 24px', borderRadius: 8, border: 'none',
          background: hovered ? `${bg}E6` : bg, color: '#fff',
          fontSize: 13, fontWeight: 600, cursor: loading ? 'wait' : 'pointer',
          opacity: disabled ? 0.5 : 1,
          display: 'flex', alignItems: 'center', gap: 8,
          transition: 'opacity 200ms ease, background 150ms ease',
          boxShadow: hovered ? `0 2px 8px ${bg}40` : 'none',
        }}
      >
        {loading ? (
          <>
            <Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} />
            {loadingLabel || label}
          </>
        ) : (
          <>
            {icon}
            {label}
          </>
        )}
      </motion.button>
    </HoverPress>
  );
}

// ─── Provider Dropdown (enhanced) ───────────────────────────────────────

function ProviderDropdown({ colors: c, providers, value, onChange, width }: {
  colors: Colors; providers: ProviderInfo[]; value: string;
  onChange: (v: string) => void; width?: number;
}) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const selected = providers.find(p => p.name === value);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={containerRef} style={{ position: 'relative', width: width || 200 }}>
      <HoverPress>
        <div
          onClick={() => setOpen(!open)}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{
            padding: '8px 14px', borderRadius: 8,
            border: `1px solid ${hovered || open ? c.border : c.borderSubtle}`,
            background: hovered ? c.surfaceHover : c.surfaceLow,
            color: c.textPrimary, fontSize: 13, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            boxShadow: hovered || open ? `0 2px 8px ${c.shadow}` : 'none',
            transition: 'background 150ms ease, border-color 150ms ease, box-shadow 150ms ease',
          }}
        >
          <span style={{ color: selected ? c.textPrimary : c.textTertiary }}>
            {selected?.display_name || value || '选择服务商'}
          </span>
          <motion.div
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
            <ChevronDown size={14} color={c.textTertiary} />
          </motion.div>
        </div>
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
              overflow: 'hidden', maxHeight: 200, overflowY: 'auto',
            }}
          >
            {providers.map((p, i) => (
              <DropdownItem
                key={p.name}
                colors={c}
                label={p.display_name}
                selected={value === p.name}
                index={i}
                onClick={() => { onChange(p.name); setOpen(false); }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DropdownItem({ colors: c, label, selected, index, onClick }: {
  colors: Colors; label: string; selected: boolean; index: number; onClick: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
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
      {label}
    </motion.div>
  );
}

// ─── Type Filter Chip ──────────────────────────────────────────────────

function TypeFilterChip({ colors: c, label, value, selected, onClick }: {
  colors: Colors; label: string; value: string; selected: string; onClick: (v: string) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const isActive = selected === value;
  return (
    <motion.div
      whileTap={{ scale: 0.95 }}
      transition={spring}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onClick(value)}
      style={{
        padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
        fontSize: 12, fontWeight: 600,
        background: isActive ? `${c.primary}18` : hovered ? c.surfaceHover : c.surfaceLow,
        border: `1px solid ${isActive ? `${c.primary}80` : hovered ? c.border : c.borderSubtle}`,
        borderWidth: isActive ? 1.5 : 1,
        color: isActive ? c.primary : c.textPrimary,
        boxShadow: (isActive || hovered) ? `0 ${hovered ? 3 : 2}px ${hovered ? 8 : 6}px ${c.shadow}` : 'none',
        transition: 'all 150ms ease-out',
      }}
    >
      {label}
    </motion.div>
  );
}

// ─── Result Card (elastic entrance) ────────────────────────────────────

function ResultCard({ colors: c, type, children }: {
  colors: Colors; type: 'success' | 'error' | 'info'; children: React.ReactNode;
}) {
  const colorMap = { success: c.success, error: c.error, info: c.info };
  const color = colorMap[type];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', damping: 12, stiffness: 200 }}
      style={{
        marginTop: 14, padding: 14, borderRadius: 8,
        border: `1px solid ${color}4D`,
        background: `${color}0F`,
      }}
    >
      {children}
    </motion.div>
  );
}

// ─── Panel 1: Manual Check ─────────────────────────────────────────────

function ManualCheckPanel({ colors: c, providers }: { colors: Colors; providers: ProviderInfo[] }) {
  const [key, setKey] = useState('');
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState('');

  const check = async () => {
    if (!key.trim()) return;
    setLoading(true); setResult(null); setError('');
    try {
      const r = await api.checkSingle(key.trim(), provider || undefined, baseUrl || undefined, model || undefined);
      setResult(r);
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <Panel colors={c} icon={<ShieldCheck size={16} />} title="手动检测">
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <div style={{ flex: 3 }}>
          <Input
            colors={c}
            value={key}
            onChange={e => setKey(e.target.value)}
            placeholder="输入 API Key"
            prefixIcon={<KeyRound size={15} />}
            mono
          />
        </div>
        <ProviderDropdown colors={c} providers={providers} value={provider} onChange={setProvider} />
        <div style={{ flex: 2 }}>
          <Input
            colors={c}
            value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)}
            placeholder="自定义 Base URL (可选)"
          />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 12 }}>
        <div style={{ flex: 2 }}>
          <Input
            colors={c}
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder="指定模型 (可选，如 gpt-4o)"
          />
        </div>
      </div>
      <div style={{ marginTop: 14 }}>
        <Btn colors={c} label="检测" loadingLabel="检测中..." loading={loading} disabled={!key.trim()} onClick={check} />
      </div>

      {result && (
        <ResultCard colors={c} type={result.status === 'valid' ? 'success' : 'error'}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {result.status === 'valid' ? <Check size={22} color={c.success} /> : <XIcon size={22} color={c.error} />}
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, color: result.status === 'valid' ? c.success : c.error, fontSize: 13 }}>
                {result.status === 'valid' ? '有效' : '无效'}
              </div>
              {result.latency_ms != null && (
                <div style={{ fontSize: 12, color: c.textTertiary, marginTop: 2 }}>延迟: {result.latency_ms}ms</div>
              )}
              {result.error && <div style={{ fontSize: 12, color: c.error, marginTop: 2 }}>{result.error}</div>}
            </div>
          </div>
        </ResultCard>
      )}
      {error && (
        <div style={{ marginTop: 8, fontSize: 12, color: c.error }}>{error}</div>
      )}
    </Panel>
  );
}

// ─── Panel 2: Batch Check ──────────────────────────────────────────────

function BatchCheckPanel({ colors: c, addToast }: { colors: Colors; addToast: (type: 'success' | 'error', msg: string, detail?: string) => void }) {
  const [input, setInput] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckBatchResponse | null>(null);

  const check = async () => {
    const keys = input.split('\n').map(k => k.trim()).filter(Boolean);
    if (!keys.length) return;
    setLoading(true); setResult(null);
    try {
      const r = await api.checkBatch(keys.map(k => ({ key: k })), baseUrl || undefined);
      setResult(r);
    } catch (e: any) {
      addToast('error', '批量检测失败', e.message);
    } finally { setLoading(false); }
  };

  return (
    <Panel colors={c} icon={<ListChecks size={16} />} title="批量检测">
      <Textarea
        colors={c}
        value={input}
        onChange={e => setInput(e.target.value)}
        placeholder="每行一个 API Key"
        rows={4}
      />
      <div style={{ marginTop: 10 }}>
        <Input
          colors={c}
          value={baseUrl}
          onChange={e => setBaseUrl(e.target.value)}
          placeholder="自定义 Base URL (可选，如 https://api.example.com/v1)"
        />
      </div>
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
        <Btn colors={c} label="批量检测" loadingLabel="检测中..." loading={loading} disabled={!input.trim()} onClick={check} />
      </div>

      {result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', damping: 12, stiffness: 200 }} style={{ marginTop: 14 }}>
          <div style={{
            padding: 14, borderRadius: 8,
            background: c.surfaceLow, border: `1px solid ${c.borderSubtle}`,
          }}>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              {[
                { label: '总计', val: result.summary.total, color: c.info },
                { label: '有效', val: result.summary.valid, color: c.success },
                { label: '无效', val: result.summary.invalid, color: c.error },
                { label: '错误', val: result.summary.error, color: c.warning },
              ].map(s => (
                <motion.div
                  key={s.label}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ type: 'spring', damping: 12, stiffness: 200 }}
                  style={{ padding: '6px 10px', borderRadius: 6, background: `${s.color}1A` }}
                >
                  <span style={{ fontSize: 11, color: c.textTertiary }}>{s.label}</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: s.color, marginLeft: 6 }}>{s.val}</span>
                </motion.div>
              ))}
            </div>
            <div style={{ maxHeight: 200, overflow: 'auto' }}>
              {result.results.slice(0, 10).map((r, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '4px 0', borderBottom: `1px solid ${c.borderSubtle}`,
                }}>
                  <span style={{ fontFamily: 'Consolas', fontSize: 11, color: c.textSecondary, flex: 1 }}>{r.key_masked}</span>
                  <span style={{ fontSize: 11, color: c.textTertiary }}>{r.provider}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 4,
                    background: `${r.status === 'valid' ? c.success : c.error}1F`,
                    color: r.status === 'valid' ? c.success : c.error,
                  }}>{r.status}</span>
                  {r.latency_ms && <span style={{ fontSize: 11, color: c.textTertiary }}>{r.latency_ms}ms</span>}
                </div>
              ))}
              {result.results.length > 10 && (
                <div style={{ fontSize: 11, color: c.textTertiary, padding: '4px 0' }}>
                  ... 还有 {result.results.length - 10} 条
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </Panel>
  );
}

// ─── Panel 3: Models ───────────────────────────────────────────────────

function ModelsPanel({ colors: c, providers, addToast }: {
  colors: Colors; providers: ProviderInfo[]; addToast: (type: 'success' | 'error', msg: string, detail?: string) => void;
}) {
  const [key, setKey] = useState('');
  const [provider, setProvider] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ModelsResponse | null>(null);
  const [capabilities, setCapabilities] = useState<Record<string, any> | null>(null);
  const [checkingModels, setCheckingModels] = useState(false);
  const [sseProgress, setSseProgress] = useState(0);
  const [sseTotal, setSseTotal] = useState(0);
  const [sseCurrent, setSseCurrent] = useState(0);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const query = async () => {
    setLoading(true); setResult(null); setCapabilities(null);
    try {
      const r = await api.getModels({ provider: provider || undefined, type_filter: typeFilter, key: key || undefined });
      setResult(r);
      if (r.models.length > 0) {
        try {
          const cap = await api.getModelCapabilities(r.models.slice(0, 50));
          setCapabilities(cap.capabilities);
        } catch {}
      }
    } catch (e: any) {
      addToast('error', '模型查询失败', e.message);
    } finally { setLoading(false); }
  };

  const checkModels = async () => {
    if (!key.trim()) {
      addToast('error', '请输入 API Key', '可用性检查需要提供密钥');
      return;
    }
    setCheckingModels(true); setSseProgress(0); setSseTotal(0); setSseCurrent(0); setAvailableModels([]);
    const modelsSoFar = new Set<string>();
    abortRef.current = new AbortController();
    try {
      await api.checkModelsSSE(
        { provider: provider || undefined, key: key.trim() },
        (event) => {
          switch (event.type) {
            case 'progress':
              setSseCurrent(event.data.current || 0);
              setSseTotal(event.data.total || 0);
              if (event.data.total > 0) setSseProgress(event.data.current / event.data.total);
              break;
            case 'result':
              const model = event.data.model || '';
              if (model && !modelsSoFar.has(model)) {
                modelsSoFar.add(model);
                setAvailableModels(prev => [...prev, model]);
              }
              break;
            case 'model_timeout':
              addToast('error', '模型超时', `${event.data.model || '未知模型'} 响应超时，已跳过`);
              break;
            case 'serial_mode':
              addToast('success', '切换串行模式', '并发请求过多，已自动切换为串行重试');
              break;
            case 'complete':
              setSseProgress(1.0);
              break;
          }
        },
        abortRef.current.signal,
      );
    } catch {} finally { setCheckingModels(false); }
  };

  const types = [
    { val: 'all', label: '全部' },
    { val: 'vision', label: '视觉' },
    { val: 'tooluse', label: '工具' },
    { val: 'reasoning', label: '推理' },
    { val: 'websearch', label: '搜索' },
    { val: 'embedding', label: '嵌入' },
    { val: 'rerank', label: '重排' },
    { val: 'free', label: '免费' },
  ];

  return (
    <Panel colors={c} icon={<Bot size={16} />} title="模型查询">
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <Input
            colors={c}
            value={key}
            onChange={e => setKey(e.target.value)}
            placeholder="API Key (可选，用于实时查询)"
            prefixIcon={<KeyRound size={15} />}
            mono
          />
        </div>
        <ProviderDropdown colors={c} providers={providers} value={provider} onChange={setProvider} />
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
        {types.map(t => (
          <TypeFilterChip key={t.val} colors={c} label={t.label} value={t.val} selected={typeFilter} onClick={setTypeFilter} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        <Btn colors={c} label="查询模型" loadingLabel="查询中..." loading={loading} onClick={query} />
        <Btn colors={c} label="可用性检查" loadingLabel="检查中..." loading={checkingModels} disabled={!key.trim()} onClick={checkModels} variant="info" />
      </div>

      {checkingModels && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1, height: 6, borderRadius: 4, background: c.surfaceLow, overflow: 'hidden' }}>
            <motion.div
              animate={{ width: `${sseTotal > 0 ? sseProgress * 100 : 0}%` }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              style={{ height: '100%', background: c.info, borderRadius: 4 }}
            />
          </div>
          <span style={{ fontSize: 12, color: c.textTertiary }}>{sseCurrent} / {sseTotal}</span>
        </div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: 'spring', damping: 12, stiffness: 200 }} style={{ marginTop: 14 }}>
          <div style={{
            padding: 14, borderRadius: 8,
            background: c.surfaceLow, border: `1px solid ${c.borderSubtle}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{ fontSize: 12, color: c.textTertiary }}>{result.provider}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary }}>{result.total} 个模型</span>
              {result.source && (
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                  background: `${c.info}1F`, color: c.info,
                }}>{result.source}</span>
              )}
            </div>
            {result.hint && <div style={{ fontSize: 12, color: c.warning, marginBottom: 8 }}>{result.hint}</div>}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {result.models.slice(0, 50).map(m => (
                <span key={m} style={{
                  padding: '4px 8px', borderRadius: 5,
                  background: c.surface, border: `1px solid ${c.borderSubtle}`,
                  fontSize: 11, color: c.textSecondary, fontFamily: 'Consolas',
                }}>{m}</span>
              ))}
              {result.models.length > 50 && (
                <span style={{ fontSize: 11, color: c.textTertiary, padding: '4px 0' }}>
                  ... 还有 {result.models.length - 50} 个
                </span>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {capabilities && Object.keys(capabilities).length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', damping: 12, stiffness: 200 }} style={{ marginTop: 14 }}>
          <div style={{
            padding: 14, borderRadius: 8,
            background: `${c.info}0A`, border: `1px solid ${c.info}33`,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: c.info, marginBottom: 8 }}>模型能力</div>
            <div style={{ maxHeight: 200, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
              {Object.entries(capabilities).slice(0, 30).map(([model, cap]) => (
                <div key={model} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '4px 8px', borderRadius: 5, background: c.surface,
                  fontSize: 11,
                }}>
                  <span style={{ fontFamily: 'Consolas', color: c.textSecondary, flex: 1 }}>{model}</span>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {cap.vision && <span style={{ padding: '1px 5px', borderRadius: 3, background: `${c.primary}1A`, color: c.primary, fontSize: 10 }}>视觉</span>}
                    {cap.tool_use && <span style={{ padding: '1px 5px', borderRadius: 3, background: `${c.success}1A`, color: c.success, fontSize: 10 }}>工具</span>}
                    {cap.reasoning && <span style={{ padding: '1px 5px', borderRadius: 3, background: `${c.warning}1A`, color: c.warning, fontSize: 10 }}>推理</span>}
                    {cap.max_tokens && <span style={{ padding: '1px 5px', borderRadius: 3, background: `${c.textTertiary}1A`, color: c.textTertiary, fontSize: 10 }}>{cap.max_tokens} tok</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {availableModels.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: 'spring', damping: 12, stiffness: 200 }} style={{ marginTop: 14 }}>
          <div style={{
            padding: 14, borderRadius: 8,
            background: `${c.success}0A`, border: `1px solid ${c.success}33`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Check size={16} color={c.success} />
              <span style={{ fontSize: 13, fontWeight: 600, color: c.success }}>可用模型: {availableModels.length} 个</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {availableModels.map(m => (
                <span key={m} style={{
                  padding: '4px 8px', borderRadius: 5,
                  background: `${c.success}1A`, border: `1px solid ${c.success}4D`,
                  fontSize: 11, color: c.success, fontFamily: 'Consolas',
                }}>{m}</span>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </Panel>
  );
}

// ─── Panel 4: Single Key Tools ─────────────────────────────────────────

function SingleKeyToolsPanel({ colors: c, providers, addToast }: {
  colors: Colors; providers: ProviderInfo[]; addToast: (type: 'success' | 'error', msg: string, detail?: string) => void;
}) {
  const [key, setKey] = useState('');
  const [provider, setProvider] = useState('');
  const [loading, setLoading] = useState<'test' | 'balance' | 'testAll' | null>(null);
  const [testResult, setTestResult] = useState<TestSingleResponse | null>(null);
  const [balanceResult, setBalanceResult] = useState<BalanceResponse | null>(null);

  const testToken = async () => {
    if (!key.trim()) return;
    setLoading('test'); setTestResult(null);
    try {
      const r = await api.testSingle(key.trim(), provider || undefined);
      setTestResult(r);
    } catch (e: any) {
      addToast('error', '测试失败', e.message);
    } finally { setLoading(null); }
  };

  const queryBalance = async () => {
    if (!key.trim()) {
      addToast('error', '请输入 API Key');
      return;
    }
    if (!provider) {
      addToast('error', '请选择服务商', '余额查询需要指定服务商');
      return;
    }
    setLoading('balance'); setBalanceResult(null);
    try {
      const r = await api.queryBalance(key.trim(), provider);
      setBalanceResult(r);
    } catch (e: any) {
      addToast('error', '余额查询失败', e.message);
    } finally { setLoading(null); }
  };

  const testAll = async () => {
    setLoading('testAll');
    try {
      await api.testAll();
      addToast('success', '全量测试已启动', '后台正在对所有有效密钥进行测试');
    } catch (e: any) {
      addToast('error', '全量测试失败', e.message);
    } finally { setLoading(null); }
  };

  return (
    <Panel colors={c} icon={<Wrench size={16} />} title="单键工具">
      <div style={{ display: 'flex', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <Input
            colors={c}
            value={key}
            onChange={e => setKey(e.target.value)}
            placeholder="输入 API Key"
            prefixIcon={<KeyRound size={15} />}
            mono
          />
        </div>
        <ProviderDropdown colors={c} providers={providers} value={provider} onChange={setProvider} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 14 }}>
        <Btn colors={c} label="测试 Token 限制" loadingLabel="测试中..." loading={loading === 'test'} disabled={!key.trim()} onClick={testToken} />
        <Btn colors={c} label="查询余额" loadingLabel="查询中..." loading={loading === 'balance'} disabled={!key.trim() || !provider} onClick={queryBalance} variant="info" />
        <Btn colors={c} label="全量测试" loadingLabel="启动中..." loading={loading === 'testAll'} onClick={testAll} icon={<ListChecks size={15} />} />
      </div>

      {testResult && (
        <ResultCard colors={c} type={testResult.error ? 'error' : 'success'}>
          {testResult.error ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <XIcon size={20} color={c.error} />
              <span style={{ fontSize: 12, color: c.error }}>{testResult.error}</span>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 12, color: c.textTertiary, marginBottom: 8 }}>
                {testResult.provider} — <span style={{ fontFamily: 'Consolas' }}>{testResult.key_masked}</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ padding: '6px 10px', borderRadius: 6, background: `${c.info}1A` }}>
                  <span style={{ fontSize: 11, color: c.textTertiary }}>Token 限制</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: c.info, marginLeft: 6 }}>{testResult.max_tokens ?? '-'}</span>
                </div>
                <div style={{ padding: '6px 10px', borderRadius: 6, background: `${c.secondary}1A` }}>
                  <span style={{ fontSize: 11, color: c.textTertiary }}>并发数</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: c.secondary, marginLeft: 6 }}>{testResult.max_concurrency ?? '-'}</span>
                </div>
              </div>
              {testResult.models && testResult.models.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 11, color: c.textTertiary }}>模型: {testResult.models.join(', ')}</div>
              )}
            </>
          )}
        </ResultCard>
      )}

      {balanceResult && (
        <ResultCard colors={c} type={balanceResult.error ? 'error' : 'success'}>
          {balanceResult.error ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <XIcon size={20} color={c.error} />
              <span style={{ fontSize: 12, color: c.error }}>{balanceResult.error}</span>
            </div>
          ) : balanceResult.balance == null ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <AlertCircle size={20} color={c.warning} />
              <span style={{ fontSize: 13, fontWeight: 600, color: c.warning }}>该服务商不支持查询余额</span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Wallet size={22} color={c.success} />
              <div>
                <div style={{ fontSize: 12, color: c.textTertiary }}>{balanceResult.provider}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: c.textPrimary }}>
                  {balanceResult.balance} {balanceResult.currency}
                </div>
              </div>
            </div>
          )}
        </ResultCard>
      )}
    </Panel>
  );
}

// ─── Panel 5: Model-Specific Testing ───────────────────────────────────

function ModelTestPanel({ colors: c, providers, addToast }: {
  colors: Colors; providers: ProviderInfo[]; addToast: (type: 'success' | 'error', msg: string, detail?: string) => void;
}) {
  const [key, setKey] = useState('');
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [concurrency, setConcurrency] = useState('10');
  const [loading, setLoading] = useState<'token' | 'concurrency' | null>(null);
  const [tokenResult, setTokenResult] = useState<ModelTestResult | null>(null);
  const [concurrencyResult, setConcurrencyResult] = useState<ModelTestResult | null>(null);

  const testToken = async () => {
    if (!key.trim() || !model.trim()) {
      addToast('error', '请输入 API Key 和模型名称');
      return;
    }
    setLoading('token'); setTokenResult(null);
    try {
      const r = await api.testTokenModel(key.trim(), model.trim(), provider || undefined);
      setTokenResult(r);
    } catch (e: any) {
      addToast('error', 'Token 测试失败', e.message);
    } finally { setLoading(null); }
  };

  const testConcurrency = async () => {
    if (!key.trim() || !model.trim()) {
      addToast('error', '请输入 API Key 和模型名称');
      return;
    }
    setLoading('concurrency'); setConcurrencyResult(null);
    try {
      const r = await api.testConcurrencyModel(
        key.trim(), model.trim(), provider || undefined,
        parseInt(concurrency) || 10,
      );
      setConcurrencyResult(r);
    } catch (e: any) {
      addToast('error', '并发测试失败', e.message);
    } finally { setLoading(null); }
  };

  return (
    <Panel colors={c} icon={<Bot size={16} />} title="模型级测试">
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <Input
            colors={c}
            value={key}
            onChange={e => setKey(e.target.value)}
            placeholder="API Key"
            prefixIcon={<KeyRound size={15} />}
            mono
          />
        </div>
        <ProviderDropdown colors={c} providers={providers} value={provider} onChange={setProvider} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{ flex: 2 }}>
          <Input
            colors={c}
            value={model}
            onChange={e => setModel(e.target.value)}
            placeholder="模型名称 (如 gpt-4o, claude-3-opus)"
          />
        </div>
        <div style={{ flex: 1 }}>
          <Input
            colors={c}
            value={concurrency}
            onChange={e => setConcurrency(e.target.value)}
            placeholder="并发数"
            type="number"
          />
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12 }}>
        <Btn
          colors={c}
          label="测试 Token 限制"
          loadingLabel="测试中..."
          loading={loading === 'token'}
          disabled={!key.trim() || !model.trim()}
          onClick={testToken}
        />
        <Btn
          colors={c}
          label="测试并发"
          loadingLabel="测试中..."
          loading={loading === 'concurrency'}
          disabled={!key.trim() || !model.trim()}
          onClick={testConcurrency}
          variant="info"
        />
      </div>

      {tokenResult && (
        <ResultCard colors={c} type={tokenResult.error ? 'error' : 'success'}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {tokenResult.error ? (
              <>
                <XIcon size={20} color={c.error} />
                <div>
                  <div style={{ fontSize: 12, color: c.error }}>{tokenResult.error}</div>
                  <div style={{ fontSize: 11, color: c.textTertiary, marginTop: 2 }}>{tokenResult.provider} / {tokenResult.model}</div>
                </div>
              </>
            ) : (
              <>
                <Check size={20} color={c.success} />
                <div>
                  <div style={{ fontSize: 11, color: c.textTertiary }}>{tokenResult.provider} / {tokenResult.model}</div>
                  <div style={{ padding: '6px 10px', borderRadius: 6, background: `${c.info}1A`, marginTop: 6, display: 'inline-block' }}>
                    <span style={{ fontSize: 11, color: c.textTertiary }}>最大 Token</span>
                    <span style={{ fontSize: 15, fontWeight: 700, color: c.info, marginLeft: 6 }}>{tokenResult.max_tokens ?? '-'}</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </ResultCard>
      )}

      {concurrencyResult && (
        <ResultCard colors={c} type={concurrencyResult.error ? 'error' : 'success'}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {concurrencyResult.error ? (
              <>
                <XIcon size={20} color={c.error} />
                <div>
                  <div style={{ fontSize: 12, color: c.error }}>{concurrencyResult.error}</div>
                  <div style={{ fontSize: 11, color: c.textTertiary, marginTop: 2 }}>{concurrencyResult.provider} / {concurrencyResult.model}</div>
                </div>
              </>
            ) : (
              <>
                <Check size={20} color={c.success} />
                <div>
                  <div style={{ fontSize: 11, color: c.textTertiary }}>{concurrencyResult.provider} / {concurrencyResult.model}</div>
                  <div style={{ padding: '6px 10px', borderRadius: 6, background: `${c.secondary}1A`, marginTop: 6, display: 'inline-block' }}>
                    <span style={{ fontSize: 11, color: c.textTertiary }}>最大并发</span>
                    <span style={{ fontSize: 15, fontWeight: 700, color: c.secondary, marginLeft: 6 }}>{concurrencyResult.max_concurrency ?? '-'}</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </ResultCard>
      )}
    </Panel>
  );
}

// ─── Panel 6: Signature Report ─────────────────────────────────────────

function SignatureReportPanel({ colors: c, addToast }: {
  colors: Colors; addToast: (type: 'success' | 'error', msg: string, detail?: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<SignatureReport | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const runReport = async () => {
    setLoading(true); setReport(null);
    try {
      const r = await api.getSignatureReport();
      setReport(r);
    } catch (e: any) {
      addToast('error', '签名报告生成失败', e.message);
    } finally { setLoading(false); }
  };

  const toggleExpand = (provider: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(provider)) next.delete(provider);
      else next.add(provider);
      return next;
    });
  };

  const rateColor = (rate: number) => {
    if (rate === 1) return c.success;
    if (rate >= 0.5) return c.warning;
    return c.error;
  };

  return (
    <Panel colors={c} icon={<ShieldCheck size={16} />} title="签名验证报告">
      <div style={{ fontSize: 12, color: c.textTertiary, marginBottom: 14 }}>
        测试每个服务商的错误签名识别能力，用于验证密钥检测的准确性
      </div>
      <Btn
        colors={c}
        label="生成报告"
        loadingLabel="正在测试所有服务商..."
        loading={loading}
        onClick={runReport}
      />

      {report && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', damping: 12, stiffness: 200 }}
          style={{ marginTop: 14 }}
        >
          {/* Summary */}
          <div style={{
            padding: 14, borderRadius: 8,
            background: c.surfaceLow, border: `1px solid ${c.borderSubtle}`,
            marginBottom: 12,
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary, marginBottom: 10 }}>摘要</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {[
                { label: '服务商', val: report.summary.total_providers, color: c.info },
                { label: '完全匹配', val: report.summary.full_match, color: c.success },
                { label: '部分匹配', val: report.summary.partial_match, color: c.warning },
                { label: '未匹配', val: report.summary.no_match, color: c.error },
                { label: '有冲突', val: report.summary.has_conflicts, color: c.warning },
                { label: '新签名', val: report.summary.has_new_signatures, color: c.info },
              ].map(s => (
                <div key={s.label} style={{ padding: '6px 10px', borderRadius: 6, background: `${s.color}1A` }}>
                  <span style={{ fontSize: 11, color: c.textTertiary }}>{s.label}</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: s.color, marginLeft: 6 }}>{s.val}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Results */}
          <div style={{ maxHeight: 400, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {report.results.map((r) => {
              const isExpanded = expanded.has(r.provider);
              return (
                <div
                  key={r.provider}
                  style={{
                    padding: '10px 12px', borderRadius: 8,
                    background: c.surface, border: `1px solid ${c.borderSubtle}`,
                    cursor: 'pointer',
                  }}
                  onClick={() => toggleExpand(r.provider)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: r.status_code ? (r.unique_signatures.match_rate === 1 ? c.success : r.unique_signatures.match_rate > 0 ? c.warning : c.error) : c.textTertiary,
                    }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: c.textPrimary, flex: 1 }}>{r.provider}</span>
                    {r.status_code && (
                      <span style={{ fontSize: 11, color: c.textTertiary, fontFamily: 'Consolas' }}>{r.status_code}</span>
                    )}
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                      background: `${rateColor(r.unique_signatures.match_rate)}1F`,
                      color: rateColor(r.unique_signatures.match_rate),
                    }}>
                      {Math.round(r.unique_signatures.match_rate * 100)}%
                    </span>
                    {r.new_signatures && r.new_signatures.length > 0 && (
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                        background: `${c.info}1F`, color: c.info,
                      }}>+{r.new_signatures.length} 新</span>
                    )}
                    {r.conflicts && r.conflicts.length > 0 && (
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                        background: `${c.warning}1F`, color: c.warning,
                      }}>冲突</span>
                    )}
                  </div>

                  {isExpanded && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${c.borderSubtle}` }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11 }}>
                        {r.unique_signatures.matched.length > 0 && (
                          <div>
                            <span style={{ color: c.success, fontWeight: 600 }}>已匹配: </span>
                            <span style={{ color: c.textSecondary }}>{r.unique_signatures.matched.join(', ')}</span>
                          </div>
                        )}
                        {r.unique_signatures.missing.length > 0 && (
                          <div>
                            <span style={{ color: c.error, fontWeight: 600 }}>缺失: </span>
                            <span style={{ color: c.textSecondary }}>{r.unique_signatures.missing.join(', ')}</span>
                          </div>
                        )}
                        {r.new_signatures && r.new_signatures.length > 0 && (
                          <div>
                            <span style={{ color: c.info, fontWeight: 600 }}>新发现: </span>
                            <span style={{ color: c.textSecondary }}>{r.new_signatures.join(', ')}</span>
                          </div>
                        )}
                        {r.conflicts && r.conflicts.length > 0 && (
                          <div>
                            <span style={{ color: c.warning, fontWeight: 600 }}>冲突: </span>
                            <span style={{ color: c.textSecondary }}>
                              {r.conflicts.map(co => `"${co.signature}" 与 ${co.other_provider}`).join('; ')}
                            </span>
                          </div>
                        )}
                        {r.error && (
                          <div>
                            <span style={{ color: c.error, fontWeight: 600 }}>错误: </span>
                            <span style={{ color: c.textSecondary }}>{r.error}</span>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </div>
              );
            })}
          </div>
        </motion.div>
      )}
    </Panel>
  );
}

// ─── Panel 7: Webhook ──────────────────────────────────────────────────

function WebhookPanel({ colors: c, addToast }: {
  colors: Colors; addToast: (type: 'success' | 'error', msg: string, detail?: string) => void;
}) {
  const [webhooks, setWebhooks] = useState<WebhookInfo[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [dialogMode, setDialogMode] = useState<'create' | 'edit' | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [url, setUrl] = useState('');
  const [secret, setSecret] = useState('');
  const [maxRetries, setMaxRetries] = useState('3');
  const [events, setEvents] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<{ url?: string; maxRetries?: string }>({});
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [showDeliveries, setShowDeliveries] = useState(false);
  const [loadingDeliveries, setLoadingDeliveries] = useState(false);

  const availableEvents = [
    'import.completed', 'check.completed', 'test.completed',
    'batch.check.completed', 'batch.test.completed',
  ];

  const load = () => {
    setLoadingList(true);
    api.getWebhooks().then(setWebhooks).catch(() => {}).finally(() => setLoadingList(false));
  };
  useEffect(() => { load(); }, []);

  const toggleEvent = (ev: string) => {
    setEvents(prev => prev.includes(ev) ? prev.filter(e => e !== ev) : [...prev, ev]);
  };

  const closeDialog = () => {
    setDialogMode(null);
    setEditingId(null);
    setUrl(''); setSecret(''); setEvents([]); setMaxRetries('3'); setErrors({});
  };

  const openCreate = () => {
    setDialogMode('create');
    setEditingId(null);
    setUrl(''); setSecret(''); setEvents([]); setMaxRetries('3'); setErrors({});
  };

  const openEdit = (wh: WebhookInfo) => {
    setDialogMode('edit');
    setEditingId(wh.id);
    setUrl(wh.url); setSecret(''); setMaxRetries(String(wh.max_retries || 3));
    setEvents(wh.events || []); setErrors({});
  };

  const validateAndSubmit = async () => {
    const errs: typeof errors = {};
    if (!url.trim()) {
      errs.url = '请输入 URL';
    } else {
      try { new URL(url.trim()); }
      catch { errs.url = 'URL 格式不正确，如 https://example.com/webhook'; }
    }
    const retries = parseInt(maxRetries);
    if (maxRetries && (isNaN(retries) || retries < 0 || retries > 10)) {
      errs.maxRetries = '请输入 0-10 之间的数字';
    }
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setLoading(true);
    try {
      const body = {
        url: url.trim(), events,
        secret: secret || undefined,
        max_retries: retries || 3,
      };
      if (dialogMode === 'edit' && editingId) {
        await api.updateWebhook(editingId, body);
        addToast('success', 'Webhook 更新成功');
      } else {
        await api.createWebhook(body);
        addToast('success', 'Webhook 创建成功');
      }
      closeDialog();
      load();
    } catch (e: any) {
      setErrors({ url: e.message });
    } finally { setLoading(false); }
  };

  const loadDeliveries = async () => {
    setLoadingDeliveries(true);
    try {
      const d = await api.getWebhookDeliveries();
      setDeliveries(d);
      setShowDeliveries(true);
    } catch (e: any) {
      addToast('error', '加载投递日志失败', e.message);
    } finally { setLoadingDeliveries(false); }
  };

  const clearDeliveries = async () => {
    try {
      await api.clearWebhookDeliveries();
      setDeliveries([]);
      addToast('success', '投递日志已清空');
    } catch (e: any) {
      addToast('error', '清空失败', e.message);
    }
  };

  const remove = async (id: string) => {
    try { await api.deleteWebhook(id); load(); }
    catch (e: any) { addToast('error', '删除失败', e.message); }
  };

  return (
    <Panel colors={c} icon={<Webhook size={16} />} title="Webhook 管理">
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 16 }}>
        <HoverPress>
          <motion.button
            whileTap={{ scale: 0.97 }}
            transition={spring}
            onClick={loadDeliveries}
            disabled={loadingDeliveries}
            style={{
              padding: '8px 14px', borderRadius: 8, border: 'none',
              background: c.surfaceLow, color: c.textSecondary,
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <History size={14} />
            投递日志
          </motion.button>
        </HoverPress>
        <HoverPress>
          <motion.button
            whileTap={{ scale: 0.97 }}
            transition={spring}
            onClick={openCreate}
            style={{
              padding: '8px 14px', borderRadius: 8, border: 'none',
              background: c.primary, color: c.onPrimary,
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Plus size={14} />
            新建
          </motion.button>
        </HoverPress>
      </div>

      {loadingList ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
          <Loader2 size={24} color={c.textTertiary} style={{ animation: 'spin 1s linear infinite' }} />
        </div>
      ) : webhooks.length === 0 ? (
        <div style={{ padding: 16, textAlign: 'center', color: c.textTertiary, fontSize: 13 }}>
          暂无 Webhook 配置
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {webhooks.map((wh, i) => (
            <WebhookItem key={wh.id} colors={c} webhook={wh} index={i} onEdit={() => openEdit(wh)} onDelete={() => remove(wh.id)} />
          ))}
        </div>
      )}

      {/* Delivery Logs */}
      <AnimatePresence>
        {showDeliveries && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ marginTop: 14, overflow: 'hidden' }}
          >
            <div style={{
              padding: 14, borderRadius: 8,
              background: c.surfaceLow, border: `1px solid ${c.borderSubtle}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary }}>投递日志 ({deliveries.length})</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  {deliveries.length > 0 && (
                    <motion.button
                      whileTap={{ scale: 0.95 }}
                      onClick={clearDeliveries}
                      style={{
                        padding: '4px 10px', borderRadius: 6, border: 'none',
                        background: `${c.error}14`, color: c.error,
                        fontSize: 11, fontWeight: 600, cursor: 'pointer',
                      }}
                    >清空</motion.button>
                  )}
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setShowDeliveries(false)}
                    style={{
                      padding: '4px 10px', borderRadius: 6, border: 'none',
                      background: 'transparent', color: c.textTertiary,
                      fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    }}
                  >收起</motion.button>
                </div>
              </div>
              {deliveries.length === 0 ? (
                <div style={{ fontSize: 12, color: c.textTertiary, textAlign: 'center', padding: 12 }}>暂无投递记录</div>
              ) : (
                <div style={{ maxHeight: 200, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {deliveries.slice(0, 20).map((d, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '6px 8px', borderRadius: 6,
                      background: c.surface,
                      fontSize: 11,
                    }}>
                      <span style={{
                        padding: '1px 6px', borderRadius: 4,
                        background: d.success ? `${c.success}1F` : `${c.error}1F`,
                        color: d.success ? c.success : c.error,
                        fontWeight: 600,
                      }}>{d.success ? '成功' : '失败'}</span>
                      <span style={{ color: c.textSecondary, flex: 1 }}>{d.event || '-'}</span>
                      {d.status_code && <span style={{ color: c.textTertiary }}>{d.status_code}</span>}
                      {d.error && <span style={{ color: c.error, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={d.error}>{d.error}</span>}
                      <span style={{ color: c.textTertiary }}>{d.timestamp ? new Date(d.timestamp).toLocaleString() : '-'}</span>
                    </div>
                  ))}
                  {deliveries.length > 20 && (
                    <div style={{ fontSize: 11, color: c.textTertiary, padding: '4px 0', textAlign: 'center' }}>
                      ... 还有 {deliveries.length - 20} 条
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create/Edit Dialog */}
      <AnimatePresence>
        {dialogMode && (
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={dialogMode === 'edit' ? '编辑 Webhook' : '新建 Webhook'}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={closeDialog}
            onKeyDown={e => e.key === 'Escape' && closeDialog()}
            style={{
              position: 'fixed', inset: 0, zIndex: 100,
              background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              onClick={e => e.stopPropagation()}
              style={{
                background: c.surface, borderRadius: 16,
                border: `1px solid ${c.borderSubtle}`,
                padding: 28, width: 440,
                boxShadow: `0 20px 60px ${c.shadow}`,
              }}
            >
              <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary, marginBottom: 20 }}>
                {dialogMode === 'edit' ? '编辑 Webhook' : '新建 Webhook'}
              </div>

              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: c.textSecondary, display: 'block', marginBottom: 6 }}>
                  URL <span style={{ color: c.error }}>*</span>
                </label>
                <Input colors={c} value={url} onChange={e => { setUrl(e.target.value); setErrors(prev => ({ ...prev, url: undefined })); }} placeholder="https://example.com/webhook" />
                {errors.url && (
                  <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} style={{ fontSize: 12, color: c.error, marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <AlertCircle size={12} />{errors.url}
                  </motion.div>
                )}
              </div>

              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: c.textSecondary, display: 'block', marginBottom: 6 }}>
                  Secret (可选)
                </label>
                <Input colors={c} value={secret} onChange={e => setSecret(e.target.value)} placeholder="HMAC 签名密钥" />
              </div>

              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: c.textSecondary, display: 'block', marginBottom: 6 }}>
                  最大重试次数
                </label>
                <Input colors={c} value={maxRetries} onChange={e => { setMaxRetries(e.target.value); setErrors(prev => ({ ...prev, maxRetries: undefined })); }} type="number" style={{ width: 100 }} />
                {errors.maxRetries && (
                  <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} style={{ fontSize: 12, color: c.error, marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <AlertCircle size={12} />{errors.maxRetries}
                  </motion.div>
                )}
              </div>

              <div style={{ marginBottom: 24 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: c.textSecondary, display: 'block', marginBottom: 8 }}>
                  订阅事件 (留空=全部)
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {availableEvents.map(ev => (
                    <TypeFilterChip
                      key={ev}
                      colors={c}
                      label={ev}
                      value={ev}
                      selected={events.includes(ev) ? ev : ''}
                      onClick={() => toggleEvent(ev)}
                    />
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
                <HoverPress>
                  <motion.button
                    whileTap={{ scale: 0.97 }}
                    transition={spring}
                    onClick={closeDialog}
                    style={{
                      padding: '10px 16px', borderRadius: 8,
                      border: 'none', background: 'transparent',
                      color: c.textTertiary, fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}
                  >取消</motion.button>
                </HoverPress>
                <Btn colors={c} label={dialogMode === 'edit' ? '保存' : '创建'} loadingLabel={dialogMode === 'edit' ? '保存中...' : '创建中...'} loading={loading} disabled={!url.trim()} onClick={validateAndSubmit} />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  );
}

// ─── Webhook Item ──────────────────────────────────────────────────────

function WebhookItem({ colors: c, webhook: wh, index, onEdit, onDelete }: {
  colors: Colors; webhook: WebhookInfo; index: number; onEdit: () => void; onDelete: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  const [deleteHovered, setDeleteHovered] = useState(false);
  const [editHovered, setEditHovered] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 24, delay: index * 0.06 }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: 12, borderRadius: 8,
        background: hovered ? c.surfaceHover : c.surfaceLow,
        border: `1px solid ${hovered ? c.border : c.borderSubtle}`,
        cursor: 'default',
        transition: 'background 150ms ease, border-color 150ms ease',
      }}
    >
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: wh.active ? c.success : c.textTertiary,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'Consolas', fontSize: 11, color: c.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {wh.url}
        </div>
        <div style={{ fontSize: 11, color: c.textTertiary, marginTop: 2 }}>
          {wh.events.length === 0 ? '所有事件' : wh.events.join(', ')}
        </div>
      </div>
      <motion.button
        whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
        transition={spring}
        onClick={onEdit}
        onMouseEnter={() => setEditHovered(true)}
        onMouseLeave={() => setEditHovered(false)}
        title="编辑 Webhook"
        style={{
          width: 30, height: 30, borderRadius: 6,
          border: 'none', background: editHovered ? `${c.primary}14` : 'transparent',
          color: editHovered ? c.primary : c.textTertiary, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 150ms ease',
        }}
      >
        <Pencil size={14} />
      </motion.button>
      <motion.button
        whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
        transition={spring}
        onClick={onDelete}
        onMouseEnter={() => setDeleteHovered(true)}
        onMouseLeave={() => setDeleteHovered(false)}
        title="删除 Webhook"
        style={{
          width: 30, height: 30, borderRadius: 6,
          border: 'none', background: deleteHovered ? `${c.error}14` : 'transparent',
          color: deleteHovered ? c.error : c.textTertiary, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 150ms ease',
        }}
      >
        <Trash2 size={14} />
      </motion.button>
    </motion.div>
  );
}
