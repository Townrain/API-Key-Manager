import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { History, FileText, RefreshCw, X, Trash2 } from 'lucide-react';
import type { Colors } from '../theme/tokens';
import { ConfirmDialog } from '../components/ConfirmDialog';

export interface ImportRecord {
  fileName: string;
  timestamp: number;
  newCount: number;
  dupeCount: number;
}

interface Props {
  colors: Colors;
  visible?: boolean;
  records: ImportRecord[];
  onReImport?: (record: ImportRecord) => void;
  onDelete?: (index: number) => void;
  onClearAll?: () => void;
}

export function ImportHistoryPage({ colors: c, records, onReImport, onDelete, onClearAll }: Props) {
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    return {
      date: `${d.getMonth() + 1}/${d.getDate()}`,
      time: `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`,
    };
  };

  return (
    <div style={{ padding: '28px 32px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: c.textPrimary, letterSpacing: -0.5, margin: 0 }}>导入历史</h1>
            <p style={{ fontSize: 13, color: c.textTertiary, margin: '4px 0 0' }}>查看所有密钥导入记录（保留最近 7 天）</p>
          </div>
          {records.length > 0 && (
            <motion.button
              whileTap={{ scale: 0.97 }}
              transition={{ type: 'spring', damping: 20, stiffness: 400 }}
              onClick={() => setConfirmClear(true)}
              style={{
                padding: '8px 14px', borderRadius: 8,
                border: `1px solid ${c.error}33`,
                background: `${c.error}14`, color: c.error,
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 6,
              }}
            >
              <Trash2 size={16} />
              清空导入历史
            </motion.button>
          )}
        </div>
      </motion.div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', marginTop: 24 }}>
        {records.length === 0 ? (
          /* Empty State (matches Flutter _buildEmpty) */
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', padding: 60,
            }}
          >
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: `${c.primary}14`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 16,
            }}>
              <History size={32} color={`${c.primary}80`} />
            </div>
            <div style={{ fontSize: 14, color: c.textSecondary, fontWeight: 500 }}>暂无导入记录</div>
            <div style={{ fontSize: 12, color: c.textTertiary, marginTop: 4 }}>导入密钥后会在这里显示记录</div>
          </motion.div>
        ) : (
          /* History Cards (matches Flutter _HistoryCard) */
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {records.map((rec, i) => {
              const { date, time } = formatDate(rec.timestamp);
              return (
                <motion.div
                  key={`${rec.timestamp}-${i}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  whileHover={{ y: 3 }}
                  transition={{
                    opacity: { duration: 0.2, delay: i * 0.04 },
                    y: { duration: 0.35, ease: [0, 0, 0.2, 1] },
                  }}
                  style={{
                    background: c.surface, borderRadius: 10,
                    border: `1px solid ${c.borderSubtle}`,
                    padding: 16,
                    display: 'flex', alignItems: 'center', gap: 14,
                    cursor: 'default',
                    transition: 'border 250ms ease-out, box-shadow 250ms ease-out',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = `${c.primary}33`;
                    e.currentTarget.style.boxShadow = `0 4px 12px ${c.shadow}`;
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = c.borderSubtle;
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  {/* File Icon (info color, matches Flutter) */}
                  <div style={{
                    width: 40, height: 40, borderRadius: 8,
                    background: `${c.info}1A`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    <FileText size={20} color={c.info} />
                  </div>

                  {/* File Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: c.textPrimary, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rec.fileName}
                    </div>
                    <div style={{ fontSize: 11, color: c.textTertiary, marginTop: 2 }}>
                      {date} {time}
                    </div>
                  </div>

                  {/* Badges (Column layout, matches Flutter _Badge) */}
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: c.success }}>
                      {rec.newCount}
                    </div>
                    <div style={{ fontSize: 10, color: c.textTertiary }}>新增</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: c.warning }}>
                      {rec.dupeCount}
                    </div>
                    <div style={{ fontSize: 10, color: c.textTertiary }}>重复</div>
                  </div>

                  {/* Action Buttons */}
                  <div style={{ display: 'flex', gap: 6 }}>
                    {onReImport && (
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                        onClick={() => onReImport(rec)}
                        style={{
                          width: 32, height: 32, borderRadius: 6,
                          border: 'none',
                          background: `${c.primary}14`,
                          color: c.primary,
                          cursor: 'pointer', display: 'flex',
                          alignItems: 'center', justifyContent: 'center',
                        }}
                        title="重新导入"
                      >
                        <RefreshCw size={16} />
                      </motion.button>
                    )}
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      transition={{ type: 'spring', damping: 20, stiffness: 400 }}
                      onClick={() => setConfirmDelete(i)}
                      style={{
                        width: 32, height: 32, borderRadius: 6,
                        border: 'none',
                        background: `${c.error}14`,
                        color: c.error,
                        cursor: 'pointer', display: 'flex',
                        alignItems: 'center', justifyContent: 'center',
                      }}
                      title="删除"
                    >
                      <X size={16} />
                    </motion.button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Delete Confirm Dialog */}
      <AnimatePresence>
        {confirmDelete !== null && (
          <ConfirmDialog
            colors={c}
            title="删除记录"
            desc="确定要删除这条导入记录吗？已导入的密钥不会被删除。"
            onConfirm={() => { onDelete?.(confirmDelete); setConfirmDelete(null); }}
            onCancel={() => setConfirmDelete(null)}
          />
        )}
      </AnimatePresence>

      {/* Clear All Confirm Dialog */}
      <AnimatePresence>
        {confirmClear && (
          <ConfirmDialog
            colors={c}
            title="确认清空"
            desc="确定要清空所有导入历史记录吗？已导入的密钥不会被删除。"
            onConfirm={() => { onClearAll?.(); setConfirmClear(false); }}
            onCancel={() => setConfirmClear(false)}
            destructive
          />
        )}
      </AnimatePresence>
    </div>
  );
}
