/**
 * Sync USWDS combo box visible inputs when the underlying <select> changes.
 */
(function (window) {
    const PLACEHOLDERS = {
        organization: 'Type an organization...',
        publisher: 'Type a publisher...',
    };

    function suggestionGroupId(key) {
        return key === 'organization' ? 'organizations' : 'publishers';
    }

    function applyPlaceholder(comboEl, key) {
        const placeholder = PLACEHOLDERS[key];
        if (!placeholder || !comboEl) {
            return;
        }
        const input = comboEl.querySelector('.usa-combo-box__input');
        if (input && !input.value) {
            input.setAttribute('placeholder', placeholder);
        }
    }

    function setSelectValue(select, value) {
        select.value = value;

        const comboEl = select.closest('.usa-combo-box');
        const input = comboEl ? comboEl.querySelector('.usa-combo-box__input') : null;
        if (input) {
            if (value) {
                const option = Array.from(select.options).find((o) => o.value === value);
                input.value = option ? option.text : '';
                comboEl.classList.add('usa-combo-box--pristine');
            } else {
                input.value = '';
                comboEl.classList.remove('usa-combo-box--pristine');
                const key = comboEl.dataset.filterCombo;
                if (key && PLACEHOLDERS[key]) {
                    input.setAttribute('placeholder', PLACEHOLDERS[key]);
                }
            }
        }

        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    window.dataGovUswdsComboSync = {
        placeholders: PLACEHOLDERS,
        suggestionGroupId,
        applyPlaceholder,
        setSelectValue,
    };
})(window);
