/**
 * Pure utility functions for the frontend.
 * Extracted from templates/index.html — no DOM access.
 */

import { ERROR_TRANSLATIONS, ERROR_TYPE_TRANSLATIONS } from './state.js';

/**
 * HTML escaping helper to prevent broken onclick handlers.
 * Replaces &, <, >, ", ' with HTML entities.
 */
export function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Attribute escaping helper.
 * Replaces &, ", <, > with HTML entities.
 */
export function escAttr(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Translate an error message to Chinese using ERROR_TRANSLATIONS.
 * Tries exact match first, then substring match.
 * Returns empty string if no translation found.
 */
export function translateError(error) {
  if (!error) return '';
  const lower = error.toLowerCase().trim();
  if (ERROR_TRANSLATIONS[lower]) return ERROR_TRANSLATIONS[lower];
  for (const [key, value] of Object.entries(ERROR_TRANSLATIONS)) {
    if (lower.includes(key)) return value;
  }
  return '';
}

/**
 * Translate an error type to Chinese using ERROR_TYPE_TRANSLATIONS.
 * Returns the original errorType if no translation found.
 */
export function translateErrorType(errorType) {
  if (!errorType) return '';
  const lower = errorType.toLowerCase().trim();
  return ERROR_TYPE_TRANSLATIONS[lower] || errorType;
}

/**
 * Map a model type code to a Chinese label.
 * Returns the original type if no mapping found.
 */
export function getTypeLabel(type) {
  const labels = {
    'all': '全部模型',
    'reasoning': '推理模型',
    'vision': '视觉模型',
    'websearch': '联网模型',
    'free': '免费模型',
    'embedding': '嵌入模型',
    'rerank': '重排模型',
    'tooluse': '工具调用',
  };
  return labels[type] || type;
}

/**
 * Parse a token error message for range info.
 * @param {string} errorMsg - The raw error message
 * @returns {{ friendly: string, maxTokens: number|null, suggestion?: string }}
 */
export function parseTokenError(errorMsg) {
  if (!errorMsg) return { friendly: '未知错误', maxTokens: null };
  const rangeMatch = errorMsg.match(/\[(\d+),\s*(\d+)\]/);
  if (rangeMatch) {
    const min = parseInt(rangeMatch[1]);
    const max = parseInt(rangeMatch[2]);
    return {
      friendly: 'Token数超出范围',
      maxTokens: max,
      suggestion: '有效范围: ' + min.toLocaleString() + ' - ' + max.toLocaleString(),
    };
  }
  if (errorMsg.includes('max_tokens')) {
    return { friendly: 'Token数无效', maxTokens: null, suggestion: '请检查Token值是否正确' };
  }
  return { friendly: errorMsg, maxTokens: null };
}
