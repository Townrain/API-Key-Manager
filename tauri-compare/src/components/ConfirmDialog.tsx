import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import type { Colors } from '../theme/tokens';

interface Props {
  colors: Colors;
  title: string;
  desc: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  destructive?: boolean;
}

export function ConfirmDialog({ colors: c, title, desc, confirmLabel, onConfirm, onCancel, destructive }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', handleKey);
    dialogRef.current?.focus();
    return () => document.removeEventListener('keydown', handleKey);
  }, [onCancel]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.4)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <motion.div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        onClick={e => e.stopPropagation()}
        style={{
          background: c.surface, borderRadius: 16,
          border: `1px solid ${c.borderSubtle}`,
          padding: 28, width: 400,
          boxShadow: `0 20px 60px ${c.shadow}`,
          outline: 'none',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 8,
            background: `${destructive ? c.error : c.warning}1F`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <AlertTriangle size={20} color={destructive ? c.error : c.warning} />
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>{title}</div>
        </div>
        <div style={{ fontSize: 14, color: c.textSecondary, marginBottom: 24, lineHeight: 1.5 }}>
          {desc}
        </div>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <motion.button
            whileTap={{ scale: 0.97 }}
            transition={{ type: 'spring', damping: 20, stiffness: 400 }}
            onClick={onCancel}
            style={{
              padding: '10px 16px', borderRadius: 8,
              border: 'none', background: 'transparent',
              color: c.textTertiary,
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}
          >取消</motion.button>
          <motion.button
            whileTap={{ scale: 0.97 }}
            transition={{ type: 'spring', damping: 20, stiffness: 400 }}
            onClick={onConfirm}
            style={{
              padding: '10px 24px', borderRadius: 8,
              border: 'none',
              background: destructive ? c.error : c.primary,
              color: c.onPrimary,
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
            }}
          >{confirmLabel || (destructive ? '清空' : '删除')}</motion.button>
        </div>
      </motion.div>
    </motion.div>
  );
}
