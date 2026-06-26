// Exact match of Flutter AppTheme colors
export const lightColors = {
  primary: '#16A34A',
  primaryDim: '#15803D',
  primaryGlow: 'rgba(22,163,74,0.13)',
  onPrimary: '#FFFFFF',
  background: '#F8FAFC',
  surface: '#FFFFFF',
  surfaceLow: '#F1F5F9',
  surfaceHover: '#E2E8F0',
  surfaceActive: '#CBD5E1',
  textPrimary: '#0F172A',
  textSecondary: '#475569',
  textTertiary: '#94A3B8',
  textInverse: '#FFFFFF',
  border: '#E2E8F0',
  borderSubtle: '#F1F5F9',
  divider: '#E2E8F0',
  error: '#DC2626',
  success: '#16A34A',
  warning: '#D97706',
  info: '#2563EB',
  shadow: 'rgba(0,0,0,0.04)',
  scrim: 'rgba(0,0,0,0.5)',
  secondary: '#64748B',
};

export const darkColors = {
  primary: '#22C55E',
  primaryDim: '#16A34A',
  primaryGlow: 'rgba(34,197,94,0.2)',
  onPrimary: '#FFFFFF',
  background: '#0B1120',
  surface: '#151D2E',
  surfaceLow: '#111827',
  surfaceHover: '#1E293B',
  surfaceActive: '#253347',
  textPrimary: '#F1F5F9',
  textSecondary: '#94A3B8',
  textTertiary: '#64748B',
  textInverse: '#0F172A',
  border: '#334155',
  borderSubtle: '#1E293B',
  divider: '#1E293B',
  error: '#EF4444',
  success: '#22C55E',
  warning: '#F59E0B',
  info: '#3B82F6',
  shadow: 'rgba(0,0,0,0.25)',
  scrim: 'rgba(0,0,0,0.7)',
  secondary: '#64748B',
};

export type Colors = typeof lightColors;

export const typography = {
  pageTitle: { fontSize: '22px', fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.5px' },
  sectionTitle: { fontSize: '15px', fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.2px' },
  subtitle: { fontSize: '13px', fontWeight: 400, lineHeight: 1.5 },
  body: { fontSize: '13px', fontWeight: 400, lineHeight: 1.5 },
  bodyBold: { fontSize: '13px', fontWeight: 600, lineHeight: 1.5 },
  label: { fontSize: '12px', fontWeight: 500, lineHeight: 1.4 },
  labelBold: { fontSize: '12px', fontWeight: 600, lineHeight: 1.4 },
  caption: { fontSize: '11px', fontWeight: 400, lineHeight: 1.4 },
  captionBold: { fontSize: '11px', fontWeight: 600, lineHeight: 1.4 },
  badge: { fontSize: '10px', fontWeight: 600, lineHeight: 1.3, letterSpacing: '0.5px' },
  button: { fontSize: '13px', fontWeight: 600, lineHeight: 1.4 },
  value: { fontSize: '28px', fontWeight: 700, lineHeight: 1.1, letterSpacing: '-1px' },
  dialogTitle: { fontSize: '18px', fontWeight: 700, lineHeight: 1.3 },
  code: { fontSize: '13px', fontWeight: 400, lineHeight: 1.5, fontFamily: 'Consolas, monospace' },
  codeSmall: { fontSize: '11px', fontWeight: 400, lineHeight: 1.4, fontFamily: 'Consolas, monospace' },
};

export const durations = {
  fast: 150,
  normal: 250,
  slow: 400,
  pageTransition: 300,
};

export const curves = {
  bouncyOut: [0.68, -0.55, 0.265, 1.55] as const,
  smooth: [0.25, 0.46, 0.45, 0.94] as const,
  snappy: [0.19, 1, 0.22, 1] as const,
  enter: [0, 0, 0.2, 1] as const,
};
