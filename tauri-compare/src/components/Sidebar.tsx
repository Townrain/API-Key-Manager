import { motion } from 'framer-motion';
import type { Colors } from '../theme/tokens';
import {
  LayoutDashboard, Key, Cloud, Wrench, FileText, History,
  Sun, Moon, KeyRound, Info,
} from 'lucide-react';
import { StaggeredFadeIn } from '../theme/animations';

type Page = 'dashboard' | 'keys' | 'providers' | 'tools' | 'logs' | 'history';

const NAV_ITEMS: { page: Page; icon: React.ElementType; label: string }[] = [
  { page: 'dashboard', icon: LayoutDashboard, label: '浠〃鐩? },
  { page: 'keys', icon: Key, label: '瀵嗛挜绠＄悊' },
  { page: 'providers', icon: Cloud, label: '鏈嶅姟鍟? },
  { page: 'tools', icon: Wrench, label: '宸ュ叿绠? },
  { page: 'logs', icon: FileText, label: '鏃ュ織' },
  { page: 'history', icon: History, label: '瀵煎叆鍘嗗彶' },
];

interface Props {
  colors: Colors;
  dark: boolean;
  currentPage: Page;
  onToggleTheme: () => void;
  onNavigate: (page: Page) => void;
}

export function Sidebar({ colors: c, dark, currentPage, onToggleTheme, onNavigate }: Props) {
  const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); action(); }
  };

  return (
    <nav role="navigation" style={{
      width: 220, flexShrink: 0,
      background: c.surfaceLow,
      borderRight: `1px solid ${c.borderSubtle}`,
      display: 'flex', flexDirection: 'column',
      height: '100%',
    }}>
      {/* Logo */}
      <div style={{ padding: '24px 20px 32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 38, height: 38, borderRadius: 10,
            background: `linear-gradient(135deg, ${c.primary}, ${c.primaryDim})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: `0 4px 16px ${c.primaryGlow}`,
          }}>
            <KeyRound size={20} color={c.onPrimary} />
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: c.textPrimary, letterSpacing: -0.3 }}>KeyHub</div>
            <div style={{ fontSize: 10, fontWeight: 600, color: c.textTertiary, letterSpacing: 0.5 }}>API Key Manager</div>
          </div>
        </div>
      </div>

      {/* Nav items */}
      <div role="tablist" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, padding: '0 12px' }}>
        {NAV_ITEMS.map(({ page, icon: Icon, label }, i) => {
          const selected = currentPage === page;
          return (
            <StaggeredFadeIn key={page} index={i} delayStep={0.05} duration={0.35} yOffset={8}>
            <motion.div
              role="tab"
              aria-selected={selected}
              tabIndex={0}
              onClick={() => onNavigate(page)}
              onKeyDown={(e) => handleKeyDown(e, () => onNavigate(page))}
              whileTap={{ scale: 0.88 }}
              whileHover={{ y: 3 }}
              transition={{
                scale: { type: 'spring', damping: 20, stiffness: 400 },
                y: { duration: 0.35, ease: [0, 0, 0.2, 1] },
              }}
              style={{
                padding: '11px 14px', borderRadius: 8,
                cursor: 'pointer', position: 'relative',
                display: 'flex', alignItems: 'center', gap: 12,
                background: selected ? `${c.primary}2E` : 'transparent',
                border: selected ? `1.5px solid ${c.primary}73` : '1.5px solid transparent',
                boxShadow: selected ? `0 4px 20px ${c.primary}1F` : 'none',
                transition: 'all 250ms cubic-bezier(0.25,0.46,0.45,0.94)',
              }}
              onMouseEnter={e => {
                if (!selected) e.currentTarget.style.background = c.surfaceHover;
              }}
              onMouseLeave={e => {
                if (!selected) e.currentTarget.style.background = 'transparent';
              }}
            >
              {/* Left highlight bar */}
              <motion.div
                initial={false}
                animate={{
                  height: selected ? 20 : 0,
                  opacity: selected ? 1 : 0,
                }}
                transition={{ duration: 0.5, ease: [0.68, -0.55, 0.265, 1.55] }}
                style={{
                  position: 'absolute', left: 0, top: '50%',
                  transform: 'translateY(-50%)',
                  width: 3, borderRadius: 2,
                  background: c.primary,
                  boxShadow: selected ? `0 0 8px ${c.primary}99` : 'none',
                }}
              />
              <motion.div
                initial={false}
                animate={{ scale: selected ? 1 : 0.6, opacity: selected ? 1 : 0.6 }}
                transition={{ duration: 0.5, ease: [0.68, -0.55, 0.265, 1.55] }}
              >
                <Icon size={20} color={selected ? c.primary : c.textSecondary} />
              </motion.div>
              <motion.span
                initial={false}
                animate={{
                  color: selected ? c.textPrimary : c.textSecondary,
                  fontWeight: selected ? 600 : 400,
                }}
                transition={{ duration: 0.25 }}
                style={{ fontSize: 13 }}
              >
                {label}
              </motion.span>
            </motion.div>
            </StaggeredFadeIn>
          );
        })}
      </div>

      {/* Footer */}
      <div style={{ padding: '0 12px', display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: 16 }}>
        {/* Theme toggle */}
        <motion.div
          role="button"
          tabIndex={0}
          aria-label={dark ? '鍒囨崲鍒颁寒鑹叉ā寮? : '鍒囨崲鍒版殫鑹叉ā寮?}
          whileTap={{ scale: 0.88 }}
          whileHover={{ y: 2 }}
          transition={{
            scale: { type: 'spring', damping: 20, stiffness: 400 },
            y: { duration: 0.35, ease: [0, 0, 0.2, 1] },
          }}
          onClick={onToggleTheme}
          onKeyDown={(e) => handleKeyDown(e, onToggleTheme)}
          style={{
            padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
            background: c.surfaceLow,
            border: `1px solid ${c.borderSubtle}`,
            display: 'flex', alignItems: 'center', gap: 12,
            transition: 'all 250ms ease',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = c.surfaceHover;
            e.currentTarget.style.borderColor = c.border;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = c.surfaceLow;
            e.currentTarget.style.borderColor = c.borderSubtle;
          }}
        >
          <motion.div
            key={dark ? 'sun' : 'moon'}
            initial={{ rotate: -90, scale: 0.6, opacity: 0 }}
            animate={{ rotate: 0, scale: 1, opacity: 1 }}
            transition={{ duration: 0.25, ease: [0.68, -0.55, 0.265, 1.55] }}
          >
            {dark ? <Sun size={20} color={c.warning} /> : <Moon size={20} color={c.textSecondary} />}
          </motion.div>
          <span style={{ fontSize: 13, color: c.textSecondary }}>{dark ? '浜壊妯″紡' : '鏆楄壊妯″紡'}</span>
        </motion.div>

        {/* Connection status */}
        <div style={{
          padding: '8px 12px', borderRadius: 8,
          background: c.surfaceLow,
          border: `1px solid ${c.borderSubtle}`,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: c.success,
            boxShadow: `0 0 6px ${c.success}66`,
          }} />
          <span style={{ flex: 1, fontSize: 11, color: c.textSecondary }}>鍚庣宸茶繛鎺?/span>
          <span style={{ fontFamily: 'Consolas', fontSize: 10, color: c.textTertiary }}>:18001</span>
        </div>

        {/* Version */}
        <div style={{
          padding: 12, borderRadius: 8,
          background: c.surface,
          border: `1px solid ${c.borderSubtle}`,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <Info size={16} color={c.textTertiary} />
          <span style={{ fontSize: 11, color: c.textTertiary }}>v5.0.1</span>
        </div>
      </div>
    </nav>
  );
}
