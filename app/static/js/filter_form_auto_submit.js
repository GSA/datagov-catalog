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

            if (typeof this.form.requestSubmit === 'function') {
                this.form.requestSubmit();
            } else {
                this.form.submit();
            }
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
