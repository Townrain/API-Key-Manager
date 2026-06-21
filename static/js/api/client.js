/**
 * API client — shared fetch logic for all API modules.
 * Handles error interception and JSON parsing.
 */

export async function safeFetch(url, options) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    let msg = `服务器错误 (${resp.status})`;
    try { const j = await resp.json(); if (j.error) { msg = (typeof j.error === 'object') ? (j.error.message || JSON.stringify(j.error)) : j.error; } } catch {}
    throw new Error(msg);
  }
  const ct = resp.headers.get('content-type') || '';
  if (!ct.includes('application/json')) throw new Error('服务器返回了非 JSON 响应');
  return resp.json();
}
