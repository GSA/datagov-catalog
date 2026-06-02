/*
 * Filter dropdown bar: facet panels, deferred Apply/Clear, and combo-box wiring.
 *
 * Facets use data-filter-defer on the root element (see filter_bar.html). While a
 * deferred panel is open, filter_form_auto_submit suppresses per-change submits
 * until Apply (force submit) or an explicit force path (e.g. keyword chip remove).
 */
(function (window, document) {
    const MOBILE_QUERY = '(max-width: 39.99em)';
    const VIEWPORT_MARGIN = 8;

    const FACET_CLEAR = {
        keywords: 'controller',
        geography: 'controller',
        organization: 'combo',
        publisher: 'combo',
        org_type: 'native',
        spatial: 'native',
    };

    function isMobile() {
        return window.matchMedia(MOBILE_QUERY).matches;
    }

    function autoSubmitController() {
        return window.dataGovFilterFormAutoSubmit || null;
    }

    function setDeferred(deferred) {
        const controller = autoSubmitController();
        if (controller) {
            controller.deferred = deferred;
        }
    }

    function submitFilters() {
        const submit = window.dataGovFilterSubmit;
        if (submit && typeof submit.request === 'function') {
            submit.request(null, { force: true });
            return;
        }
        const form = document.getElementById('filter-form');
        if (form) {
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }
    }

    const comboSync = window.dataGovUswdsComboSync;
    const launcher = window.dataGovThirdPartyLauncher;
    const filterControllers = window.dataGovFilterControllers;

    const bar = {
        facets: [],
        backdrop: null,
        openFacet: null,

        init() {
            const facetEls = Array.from(document.querySelectorAll('.filter-facet'));
            if (!facetEls.length) {
                return;
            }
            this.backdrop = document.querySelector('[data-filter-backdrop]');

            facetEls.forEach((el) => {
                const key = el.dataset.filterKey;
                const deferred = el.dataset.filterDefer !== 'false';
                const button = el.querySelector('.filter-facet__button');
                const panel = el.querySelector('.filter-facet__panel');
                const facet = { key, deferred, el, button, panel };
                this.facets.push(facet);

                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggle(facet);
                });

                const closeBtn = el.querySelector('[data-filter-close]');
                if (closeBtn) {
                    closeBtn.addEventListener('click', () => this.close());
                }
                const applyBtn = el.querySelector('[data-filter-apply]');
                if (applyBtn) {
                    applyBtn.addEventListener('click', () => {
                        this.close({ skipDeferReset: true });
                        submitFilters();
                    });
                }
                const clearBtn = el.querySelector('[data-filter-clear]');
                if (clearBtn) {
                    clearBtn.addEventListener('click', () => {
                        this.clearFacet(facet);
                        this.close({ skipDeferReset: true });
                        submitFilters();
                    });
                }

                this.setupComboFacet(facet);
            });

            if (this.backdrop) {
                this.backdrop.addEventListener('click', () => this.close());
            }

            document.addEventListener('click', (e) => {
                if (!this.openFacet) {
                    return;
                }
                if (!this.openFacet.el.contains(e.target)) {
                    this.close();
                }
            });

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.openFacet) {
                    const toFocus = this.openFacet.button;
                    this.close();
                    if (toFocus) {
                        toFocus.focus();
                    }
                }
            });

            window.addEventListener('resize', () => {
                if (this.openFacet && !isMobile()) {
                    this.positionPanel(this.openFacet);
                }
            });

            this.initSortControl();
            this.initBarToggle();
        },

        initBarToggle() {
            const toggle = document.querySelector('[data-filter-bar-toggle]');
            if (!toggle) {
                return;
            }
            const barEl = document.getElementById(toggle.getAttribute('aria-controls'));
            if (!barEl) {
                return;
            }
            toggle.addEventListener('click', () => {
                const expanded = barEl.classList.toggle('filter-bar--expanded');
                toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            });
        },

        toggle(facet) {
            if (this.openFacet === facet) {
                this.close();
            } else {
                this.open(facet);
            }
        },

        open(facet) {
            if (this.openFacet) {
                this.close();
            }
            this.openFacet = facet;
            facet.button.setAttribute('aria-expanded', 'true');
            facet.panel.hidden = false;
            facet.el.classList.add('filter-facet--open');
            setDeferred(facet.deferred);
            if (launcher && typeof launcher.setHidden === 'function') {
                launcher.setHidden(true);
            }

            if (this.backdrop && isMobile()) {
                this.backdrop.hidden = false;
                document.body.classList.add('filter-bar-open');
            }

            facet.panel.style.left = '';
            facet.panel.style.right = '';
            if (!isMobile()) {
                this.positionPanel(facet);
            }

            if (facet.key === 'geography' && window.dataGovGeographyAutocomplete) {
                window.dataGovGeographyAutocomplete.onFacetOpened();
            }

            const focusable = facet.panel.querySelector(
                'input, select, textarea, button, [tabindex]:not([tabindex="-1"])'
            );
            if (focusable) {
                focusable.focus({ preventScroll: true });
            }
        },

        close(options = {}) {
            const facet = this.openFacet;
            if (!facet) {
                return;
            }
            facet.button.setAttribute('aria-expanded', 'false');
            facet.panel.hidden = true;
            facet.el.classList.remove('filter-facet--open');
            facet.panel.style.left = '';
            facet.panel.style.right = '';
            this.openFacet = null;

            if (this.backdrop) {
                this.backdrop.hidden = true;
            }
            document.body.classList.remove('filter-bar-open');
            if (launcher && typeof launcher.setHidden === 'function') {
                launcher.setHidden(false);
            }

            if (!options.skipDeferReset) {
                setDeferred(false);
            }
        },

        positionPanel(facet) {
            const panel = facet.panel;
            const rect = panel.getBoundingClientRect();
            const viewportWidth = document.documentElement.clientWidth;
            if (rect.right > viewportWidth - VIEWPORT_MARGIN) {
                panel.style.left = 'auto';
                panel.style.right = '0';
            }
        },

        clearFacet(facet) {
            const strategy = FACET_CLEAR[facet.key] || 'native';
            if (strategy === 'controller' && filterControllers) {
                filterControllers.clearStaged(facet.key);
                return;
            }
            if (strategy === 'combo') {
                this.clearComboInPanel(facet.panel);
                return;
            }
            this.clearNativeInputsInPanel(facet.panel);
        },

        clearNativeInputsInPanel(panel) {
            panel.querySelectorAll('input[type="checkbox"]').forEach((input) => {
                input.checked = false;
            });
            const radios = {};
            panel.querySelectorAll('input[type="radio"]').forEach((input) => {
                radios[input.name] = radios[input.name] || [];
                radios[input.name].push(input);
            });
            Object.values(radios).forEach((group) => {
                const fallback = group.find((r) => r.value === '') || group[0];
                group.forEach((r) => {
                    r.checked = r === fallback;
                });
            });
        },

        clearComboInPanel(panel) {
            const comboEl = panel.querySelector('.usa-combo-box');
            const comboSelect = comboEl ? comboEl.querySelector('select') : null;
            if (comboSelect && comboSelect.value !== '' && comboSync) {
                comboSync.setSelectValue(comboSelect, '');
            }
        },

        setupComboFacet(facet) {
            const comboEl = facet.panel.querySelector('.usa-combo-box');
            const select = comboEl ? comboEl.querySelector('select') : null;
            if (!select || !comboSync) {
                return;
            }

            comboSync.applyPlaceholder(comboEl, facet.key);

            if (!facet.deferred) {
                select.addEventListener('change', () => {
                    this.close({ skipDeferReset: true });
                    submitFilters();
                });

                const clearInput = comboEl.querySelector('.usa-combo-box__clear-input');
                if (clearInput) {
                    clearInput.addEventListener('click', () => {
                        window.setTimeout(() => {
                            this.close({ skipDeferReset: true });
                            submitFilters();
                        }, 0);
                    });
                }
            }

            const groupId = 'suggested-' + comboSync.suggestionGroupId(facet.key);
            const group = facet.el.querySelector('#' + groupId);
            if (group) {
                group.querySelectorAll('[data-org-slug], [data-publisher-name]').forEach((btn) => {
                    btn.addEventListener('click', () => {
                        const value = btn.dataset.orgSlug || btn.dataset.publisherName || '';
                        comboSync.setSelectValue(select, value);
                    });
                });
            }
        },

        initSortControl() {
            const sortSelect = document.getElementById('sort-select');
            if (!sortSelect) {
                return;
            }
            sortSelect.addEventListener('change', () => {
                const formId = sortSelect.getAttribute('form') || 'main-search-form';
                const form = document.getElementById(formId);
                if (!form) {
                    return;
                }
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                } else {
                    form.submit();
                }
            });
        },
    };

    document.addEventListener('DOMContentLoaded', () => bar.init());

    window.dataGovFilterDropdowns = bar;
})(window, document);
