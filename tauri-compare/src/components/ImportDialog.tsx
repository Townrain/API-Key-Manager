import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileCheck, X, AlertCircle, CheckCircle, FileJson } from 'lucide-react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { invoke } from '@tauri-apps/api/core';
import type { Colors } from '../theme/tokens';
import { api } from '../api/client';

interface Props {
  colors: Colors;
  open: boolean;
  onClose: () => void;
  onImportSuccess?: (fileName: string, newCount: number, dupeCount: number) => void;
}

type Stage = 'select' | 'uploading' | 'done' | 'error';

export function ImportDialog({ colors: c, open, onClose, onImportSuccess }: Props) {
  const [stage, setStage] = useState<Stage>('select');
  const [fileName, setFileName] = useState('');
  const [fileText, setFileText] = useState('');
  const [dragging, setDragging] = useState(false);
  const [newCount, setNewCount] = useState(0);
  const [dupeCount, setDupeCount] = useState(0);
  const [errorMsg, setErrorMsg] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  // Tauri native file-drop events
  useEffect(() => {
    if (!open) return;

    let unlisten: (() => void) | null = null;

    getCurrentWindow().onDragDropEvent((event) => {
      if (event.payload.type === 'over') {
        setDragging(true);
      } else if (event.payload.type === 'leave') {
        setDragging(false);
      } else if (event.payload.type === 'drop') {
        setDragging(false);
        const paths = event.payload.paths;
        if (!paths.length) return;

        const path = paths[0];
        const name = path.split(/[/\\]/).pop() || path;

        invoke<string>('read_file_text', { path })
          .then((text) => {
            setFileName(name);
            setFileText(text);
            setStage('select');
            setErrorMsg('');
          })
          .catch((err: any) => {
            setErrorMsg('无法读取文件: ' + (err.message || err));
            setStage('error');
          });
      }
    }).then(fn => { unlisten = fn; });

    return () => { unlisten?.(); };
  }, [open]);

  const reset = () => {
    setStage('select');
    setFileName('');
    setFileText('');
    setDragging(false);
    setNewCount(0);
    setDupeCount(0);
    setErrorMsg('');
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const pickFile = () => fileRef.current?.click();

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
      const text = await file.text();
      setFileText(text);
      setStage('select');
      setErrorMsg('');
    }
    e.target.value = '';
  };

  const doImport = async () => {
    if (!fileName || !fileText) return;
    setStage('uploading');
    try {
      const result = await api.importUpload(fileName, fileText);
      const n = result.new_count ?? result.new ?? 0;
      const d = result.dupe_count ?? result.dupes ?? 0;
      setNewCount(n);
      setDupeCount(d);
      setStage('done');
      onImportSuccess?.(fileName, n, d);
    } catch (err: any) {
      setErrorMsg(err.message || '导入失败');
      setStage('error');
    }
  };

  const dropBg = dragging ? `${c.primary}12` : fileName ? `${c.primary}0A` : c.surfaceLow;
  const dropBorder = dragging ? `${c.primary}66` : fileName ? `${c.primary}66` : c.borderSubtle;
  const dropBorderW = dragging ? 2 : 1;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={handleClose}
          style={{
            position: 'fixed', inset: 0, zIndex: 300,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ type: 'spring', damping: 20, stiffness: 300 }}
            onClick={e => e.stopPropagation()}
            style={{
              width: 440, borderRadius: 16, padding: 28,
              background: c.surface, border: `1px solid ${c.borderSubtle}`,
              boxShadow: `0 20px 60px ${c.shadow}`,
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: `${c.info}1A`, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Upload size={20} color={c.info} />
              </div>
              <span style={{ flex: 1, fontSize: 16, fontWeight: 700, color: c.textPrimary }}>导入 JSON 密钥</span>
              <motion.div
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={handleClose}
                style={{ cursor: 'pointer', padding: 4 }}
              >
                <X size={20} color={c.textTertiary} />
              </motion.div>
            </div>

            {/* Upload zone */}
            {stage !== 'done' && (
              <motion.div
                onClick={stage === 'uploading' ? undefined : pickFile}
                animate={{
                  background: dropBg,
                  borderColor: dropBorder,
                  borderWidth: dropBorderW,
                }}
                transition={{ duration: 0.2 }}
                style={{
                  borderRadius: 12, padding: '40px 24px',
                  borderStyle: 'solid',
                  cursor: stage === 'uploading' ? 'default' : 'pointer',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
                  transition: 'background 200ms ease',
                }}
              >
                {dragging ? (
                  <>
                    <FileCheck size={40} color={c.primary} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: c.primary }}>松开以导入文件</span>
                  </>
                ) : fileName ? (
                  <>
                    <FileJson size={40} color={c.primary} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: c.textPrimary }}>{fileName}</span>
                    <span style={{ fontSize: 12, color: c.textTertiary }}>支持 .json 格式</span>
                  </>
                ) : (
                  <>
                    <Upload size={40} color={c.textTertiary} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: c.textSecondary }}>点击选择文件或拖入 JSON 文件</span>
                    <span style={{ fontSize: 12, color: c.textTertiary }}>支持 .json 格式</span>
                  </>
                )}
              </motion.div>
            )}

            {/* Error banner */}
            {stage === 'error' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', damping: 15, stiffness: 250 }}
                style={{
                  marginTop: 16, padding: '12px 16px', borderRadius: 10,
                  background: `${c.error}0D`, border: `1px solid ${c.error}33`,
                  display: 'flex', alignItems: 'center', gap: 10,
                }}
              >
                <AlertCircle size={18} color={c.error} />
                <span style={{ fontSize: 13, color: c.error, flex: 1 }}>{errorMsg}</span>
              </motion.div>
            )}

            {/* Result view */}
            {stage === 'done' && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: 'spring', damping: 15, stiffness: 250 }}
                style={{
                  padding: '32px 24px', borderRadius: 12,
                  background: `${c.success}0A`, border: `1px solid ${c.success}33`,
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
                }}
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', damping: 10, stiffness: 200, delay: 0.1 }}
                >
                  <CheckCircle size={48} color={c.success} />
                </motion.div>
                <span style={{ fontSize: 16, fontWeight: 700, color: c.textPrimary }}>导入成功</span>
                <div style={{ display: 'flex', gap: 24 }}>
                  <ResultBadge colors={c} label="新增" value={newCount} type="success" />
                  <ResultBadge colors={c} label="重复" value={dupeCount} type="warning" />
                </div>
              </motion.div>
            )}

            {/* Action buttons */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 24 }}>
              {stage === 'done' ? (
                <motion.button
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ type: 'spring', damping: 15, stiffness: 250, delay: 0.2 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleClose}
                  style={{
                    width: '100%', padding: '10px 24px', borderRadius: 8,
                    border: 'none', background: c.primary, color: '#fff',
                    fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  完成
                </motion.button>
              ) : (
                <>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={handleClose}
                    style={{
                      padding: '10px 20px', borderRadius: 8,
                      border: 'none', background: 'transparent',
                      color: c.textTertiary, fontSize: 14, fontWeight: 500, cursor: 'pointer',
                    }}
                  >
                    取消
                  </motion.button>
                  <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={doImport}
                    disabled={!fileName || stage === 'uploading'}
                    style={{
                      padding: '10px 24px', borderRadius: 8,
                      border: 'none',
                      background: fileName && stage !== 'uploading' ? c.primary : `${c.primary}4D`,
                      color: '#fff', fontSize: 14, fontWeight: 600,
                      cursor: fileName && stage !== 'uploading' ? 'pointer' : 'default',
                      display: 'flex', alignItems: 'center', gap: 8,
                    }}
                  >
                    {stage === 'uploading' ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                          style={{
                            width: 16, height: 16, borderRadius: '50%',
                            border: '2px solid rgba(255,255,255,0.3)',
                            borderTopColor: '#fff',
                          }}
                        />
                        导入中...
                      </>
                    ) : '导入'}
                  </motion.button>
                </>
              )}
            </div>

            {/* Hidden file input */}
            <input
              ref={fileRef}
              type="file"
              accept=".json"
              style={{ display: 'none' }}
              onChange={handleFileInput}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ResultBadge({ colors: c, label, value, type }: { colors: Colors; label: string; value: number; type: 'success' | 'warning' }) {
  const color = type === 'success' ? c.success : c.warning;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 28, fontWeight: 700, color, letterSpacing: -1 }}>{value}</span>
      <span style={{ fontSize: 12, fontWeight: 500, color: c.textTertiary }}>{label}</span>
    </div>
  );
}
