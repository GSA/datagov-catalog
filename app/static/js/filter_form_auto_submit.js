(function (window, document) {
    function showResultsLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'search-results-loading-overlay';
        overlay.style.cssText = [
            'position: fixed',
            'inset: 0',
            'display: flex',
            'align-items: center',
            'justify-content: center',
            'background: rgba(0, 0, 0, 0.4)',
            'z-index: 9999',
        ].join('; ');

        const badge = document.createElement('div');
        badge.style.cssText = [
            'background: white',
            'border-radius: 8px',
            'padding: 1.5rem 2.5rem',
            'display: flex',
            'flex-direction: column',
            'align-items: center',
            'gap: 0.75rem',
            'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25)',
        ].join('; ');

        const spinner = document.createElement('i');
        spinner.className = 'fa fa-spinner fa-spin';
        spinner.setAttribute('aria-label', 'Loading');
        spinner.setAttribute('role', 'img');
        spinner.style.cssText = 'font-size: 2.5rem; color: #005ea2;';

        const label = document.createElement('span');
        label.textContent = 'Loading results…';
        label.style.cssText = 'font-size: 1rem; color: #1b1b1b;';

        badge.appendChild(spinner);
        badge.appendChild(label);
        overlay.appendChild(badge);
        document.body.appendChild(overlay);
    }

    const autoSubmit = {
        form: null,
        // When true, per-change submits are suppressed; the filter dropdowns
        // submit explicitly via request({ force: true }) on Apply. The bar JS
        // toggles this while a deferred panel is open.
        deferred: false,
        init(form) {
            this.form = form || null;
        },
        request(options) {
            if (!this.form) {
                return;
            }
            const force = Boolean(options && options.force);
            // While a deferred filter panel is open, hold off on submitting until
            // the user presses Apply (which calls request({ force: true })).
            if (this.deferred && !force) {
                return;
            }
            showResultsLoadingOverlay();

            const form = this.form;
            requestAnimationFrame(() => {
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        },
    };

    document.addEventListener('DOMContentLoaded', () => {
        const form = document.getElementById('filter-form');
        if (!form) {
            return;
        }

        autoSubmit.init(form);
    });

    window.dataGovFilterFormAutoSubmit = autoSubmit;
})(window, document);
