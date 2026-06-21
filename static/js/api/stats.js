/**
 * Stats API — /api/stats
 */
import { State } from '../state.js';
import { safeFetch } from './client.js';

export async function loadStats() {
  try {
    const data = await safeFetch('/api/stats');

    const animateValue = (el, nv) => {
      const cv = parseInt(el.textContent) || 0;
      if (cv === nv) return;
      const dur = 500, start = performance.now();
      const anim = (now) => {
        const p = Math.min((now - start) / dur, 1);
        el.textContent = Math.round(cv + (nv - cv) * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(anim);
      };
      requestAnimationFrame(anim);
    };

    animateValue(document.getElementById('total-keys'), data.total);
    let valid = 0, invalid = 0, error = 0;
    Object.values(data.providers).forEach(p => { valid += p.valid; invalid += p.invalid; error += p.error; });
    animateValue(document.getElementById('valid-keys'), valid);
    animateValue(document.getElementById('invalid-keys'), invalid);
    document.getElementById('providers-count').textContent = Object.keys(data.providers).length;
    document.getElementById('all-count').textContent = data.total;
    document.getElementById('valid-count').textContent = valid;
    document.getElementById('invalid-count').textContent = invalid;
    document.getElementById('error-count').textContent = error;

    const sel = document.getElementById('provider-filter');
    const cv = sel.value;
    sel.innerHTML = '<option value="">全部服务商</option>';
    Object.keys(data.providers).sort().forEach(p => { const dn = data.providers[p].display_name || p; sel.innerHTML += `<option value="${p}">${dn}</option>`; State.DISPLAY_NAMES[p] = dn; });
    sel.value = cv;
  } catch (e) {
    console.error('[KeyHub] loadStats failed:', e);
  }
}
