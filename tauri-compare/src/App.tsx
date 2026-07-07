import { useState, useCallback, useRef, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { lightColors, darkColors, type Colors } from './theme/tokens';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { KeysPage } from './pages/KeysPage';
import { ProvidersPage } from './pages/ProvidersPage';
import { ToolsPage } from './pages/ToolsPage';
import { LogsPage } from './pages/LogsPage';
import { ImportHistoryPage, type ImportRecord } from './pages/ImportHistoryPage';
import { api, setAuthToken } from './api/client';
import './App.css';

// Read auth token: window.__API_TOKEN__ (injected) > localStorage
const apiToken = (window as any).__API_TOKEN__ || localStorage.getItem('keyhub_api_token') || '';
if (apiToken) {
  setAuthToken(apiToken);
  if (!localStorage.getItem('keyhub_api_token')) {
    localStorage.setItem('keyhub_api_token', apiToken);
  }
}

type Page = 'dashboard' | 'keys' | 'providers' | 'tools' | 'logs' | 'history';

function App() {
  const [dark, setDark] = useState(false);

  const toggleTheme = useCallback(() => {
    document.documentElement.classList.add('theme-switching');
    setDark(d => !d);
    setTimeout(() => document.documentElement.classList.remove('theme-switching'), 450);
  }, []);
  const [page, setPage] = useState<Page>('dashboard');
  const [providerFilter, setProviderFilter] = useState<string | null>(null);
  const [importHistory, setImportHistory] = useState<ImportRecord[]>(() => {
    try {
      const saved = localStorage.getItem('importHistory');
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  // Persist import history to localStorage
  useEffect(() => {
    localStorage.setItem('importHistory', JSON.stringify(importHistory));
  }, [importHistory]);
  const fileRef = useRef<HTMLInputElement>(null);
  const c: Colors = dark ? darkColors : lightColors;

  useEffect(() => {
    const root = document.documentElement;
    const vars: Record<string, string> = {
      '--scrollbar-thumb': c.border,
      '--scrollbar-thumb-hover': c.textTertiary,
      '--text-primary': c.textPrimary,
      '--text-secondary': c.textSecondary,
      '--text-tertiary': c.textTertiary,
      '--surface': c.surface,
      '--surface-low': c.surfaceLow,
      '--surface-hover': c.surfaceHover,
      '--border': c.border,
      '--border-subtle': c.borderSubtle,
      '--primary': c.primary,
      '--on-primary': c.onPrimary,
      '--error': c.error,
    };
    Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
  }, [dark, c]);

  const navigateToKeys = useCallback((provider?: string) => {
    setProviderFilter(provider || null);
    setPage('keys');
  }, []);

  const handleReImport = useCallback((_record: ImportRecord) => {
    fileRef.current?.click();
  }, []);

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      const result = await api.importUpload(file.name, text);
      setImportHistory(prev => [{
        fileName: file.name,
        timestamp: Date.now(),
        newCount: result.new_count ?? result.new ?? 0,
        dupeCount: result.dupe_count ?? result.dupes ?? 0,
      }, ...prev]);
    } catch (err) {
      console.error('Import failed:', err);
    }
    e.target.value = '';
  }, []);

  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return <Dashboard colors={c} visible onNavigate={navigateToKeys} onImportSuccess={(fileName, newCount, dupeCount) => {
          setImportHistory(prev => [{ fileName, timestamp: Date.now(), newCount, dupeCount }, ...prev]);
        }} />;
      case 'keys':
        return <KeysPage colors={c} visible providerFilter={providerFilter} onImportSuccess={(fileName, newCount, dupeCount) => {
          setImportHistory(prev => [{ fileName, timestamp: Date.now(), newCount, dupeCount }, ...prev]);
        }} />;
      case 'providers':
        return <ProvidersPage colors={c} visible onNavigateToKeys={navigateToKeys} />;
      case 'tools':
        return <ToolsPage colors={c} visible />;
      case 'logs':
        return <LogsPage colors={c} visible />;
      case 'history':
        return (
          <ImportHistoryPage
            colors={c}
            visible
            records={importHistory}
            onReImport={handleReImport}
            onDelete={(i) => setImportHistory(prev => prev.filter((_, idx) => idx !== i))}
            onClearAll={() => setImportHistory([])}
          />
        );
    }
  };

  return (
    <div className="app" style={{ background: c.background, color: c.textPrimary }}>
      <Sidebar
        colors={c}
        dark={dark}
        currentPage={page}
        onToggleTheme={toggleTheme}
        onNavigate={setPage}
      />
      <main className="main-content">
        <AnimatePresence mode="wait">
          <motion.div
            key={page}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            style={{ height: '100%' }}
          >
            {renderPage()}
          </motion.div>
        </AnimatePresence>
      </main>
      <input ref={fileRef} type="file" accept=".json,.txt" style={{ display: 'none' }} onChange={handleFileChange} />
    </div>
  );
}

export default App;
