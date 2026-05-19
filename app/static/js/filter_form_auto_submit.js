(function (window, document) {
    const mapPanelStateStorageKey = 'datagov.geographyMapExpanded.nextState';
    const mapPanelId = 'geography-map-expanded-panel';

    function parseSpatialWithinValue(value) {
        if (typeof value !== 'string') {
            return true;
        }
        const normalized = value.trim().toLowerCase();
        if (['true', '1', 'yes', 'y', 'on', 'within'].includes(normalized)) {
            return true;
        }
        if (['false', '0', 'no', 'n', 'off', 'intersect', 'intersects'].includes(normalized)) {
            return false;
        }
        return true;
    }

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
        init(form) {
            this.form = form || null;
            if (this.form) {
                this.form.addEventListener('submit', () => this.captureMapPanelState());
            }
        },
        hasOpenEligibleGeographyFilter() {
            const geographyController = window.dataGovGeographyAutocomplete;
            if (
                geographyController &&
                typeof geographyController.hasOpenEligibleMapPanelState === 'function'
            ) {
                return geographyController.hasOpenEligibleMapPanelState();
            }

            if (this.form) {
                const geometryInput = this.form.querySelector(
                    'input[name="spatial_geometry"][type="hidden"]'
                );
                if (geometryInput) {
                    const withinInput = this.form.querySelector(
                        'input[name="spatial_within"][type="hidden"]'
                    );
                    const withinValue = withinInput ? withinInput.value : 'true';
                    return parseSpatialWithinValue(withinValue);
                }
            }

            try {
                const urlParams = new URLSearchParams(window.location.search);
                if (!urlParams.get('spatial_geometry')) {
                    return false;
                }
                return parseSpatialWithinValue(urlParams.get('spatial_within') || 'true');
            } catch (_err) {
                return false;
            }
        },
        captureMapPanelState() {
            if (typeof window === 'undefined' || !window.sessionStorage) {
                return;
            }

            const panel = document.getElementById(mapPanelId);
            if (!panel) {
                return;
            }

            const hasOpenEligibleGeographyFilter = this.hasOpenEligibleGeographyFilter();
            const isOpen = hasOpenEligibleGeographyFilter && !panel.hidden;
            try {
                window.sessionStorage.setItem(mapPanelStateStorageKey, isOpen ? '1' : '0');
            } catch (_err) {
                // Ignore storage errors (privacy mode, quota, disabled storage).
            }
        },
        request() {
            if (!this.form) {
                return;
            }
            this.captureMapPanelState();
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

    function attachInputAutoSubmit(form, selectorList) {
        const selectors = selectorList.join(',');
        const inputs = form.querySelectorAll(selectors);
        inputs.forEach((input) => {
            input.addEventListener('change', () => autoSubmit.request());
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const form = document.getElementById('filter-form');
        if (!form) {
            return;
        }

        autoSubmit.init(form);
        attachInputAutoSubmit(form, ['input[name="org_type"]']);
        attachInputAutoSubmit(form, ['input[name="spatial_filter"]']);
        attachInputAutoSubmit(form, ['select[name="sort"]']);
    });

    window.dataGovFilterFormAutoSubmit = autoSubmit;
})(window, document);