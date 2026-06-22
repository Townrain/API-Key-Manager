/**
 * UI helper functions — custom select, dropdown toggle, logs toggle.
 * Extracted from init.js for modular organization.
 */

export function selectCustomOption(selectId, value, label) {
    const select = document.getElementById(selectId);

    // Update hidden input
    const hiddenInput = select.querySelector('input[type=hidden]');
    if (hiddenInput) hiddenInput.value = value;

    // Update label
    const labelEl = select.querySelector('#' + selectId.replace('-select', '-label'));
    if (labelEl) labelEl.textContent = label;

    // Update selected state
    select.querySelectorAll('.custom-select-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === value);
    });

    // Close dropdown
    select.classList.remove('open');
}

export function toggleCustomSelect(selectId) {
    const select = document.getElementById(selectId);
    // Close all other selects
    document.querySelectorAll('.custom-select.open').forEach(el => {
        if (el.id !== selectId) {
            el.classList.remove('open');
        }
    });
    // Toggle current
    select.classList.toggle('open');
}

export function toggleLogs() {
    document.getElementById('logs-container').classList.toggle('collapsed');
}
