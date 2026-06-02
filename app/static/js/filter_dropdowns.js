/*
 * Filter dropdown bar interactions.
 *
 * The filter facets live in a horizontal bar under the search box. Each facet is
 * a button that toggles a panel. On wide screens the panel is a dropdown anchored
 * to its button (edge-aligned so it never overflows the viewport); on small
 * screens it becomes a bottom drawer the user can scroll.
 *
 * Most facets are "deferred": staged selections are not applied until the user
 * presses Apply. While a deferred panel is open we flip the shared auto-submit
 * controller into deferred mode so the autocomplete widgets stop submitting on
 * every change. The geography facet is not deferred — it manages its own
 * immediate submits (autocomplete selection + map Apply), so its panel has no
 * Apply/Clear footer.
 */
(function (window, document) {
    const MOBILE_QUERY = '(max-width: 39.99em)';
    const VIEWPORT_MARGIN = 8;

    function isMobile() {
        return window.matchMedia(MOBILE_QUERY).matches;
    }

    // Placeholder copy for USWDS combo box facets. Set on the enhanced text
    // input after USWDS init (data-placeholder on the wrapper is the primary
    // source; this keeps placeholders working if the server-side markup is stale).
    const COMBO_PLACEHOLDERS = {
        organization: 'Type an organization...',
        publisher: 'Type a publisher...',
    };

    function applyComboPlaceholder(comboEl, key) {
        const placeholder = COMBO_PLACEHOLDERS[key];
        if (!placeholder || !comboEl) {
            return;
        }
        const input = comboEl.querySelector('.usa-combo-box__input');
        if (input && !input.value) {
            input.setAttribute('placeholder', placeholder);
        }
    }

    // The popular-quick-pick container id for a combo facet.
    function comboSuggestionGroup(key) {
        return key === 'organization' ? 'organizations' : 'publishers';
    }

    // Set a value on a USWDS-enhanced <select> and fire a change event so the
    // submit handler runs. USWDS does NOT sync its visible text input when the
    // hidden <select> changes programmatically, so we mirror the selected
    // option's label into the input (and toggle the pristine class so the clear
    // "×" button shows) — otherwise a popular quick-pick selection would not be
    // visible in the typeahead.
    function setComboValue(select, value) {
        select.value = value;

        const comboEl = select.closest('.usa-combo-box');
        const input = comboEl ? comboEl.querySelector('.usa-combo-box__input') : null;
        if (input) {
            if (value) {
                const option = Array.from(select.options).find((o) => o.value === value);
                input.value = option ? option.text : '';
                // USWDS marks a combo box "pristine" when the input matches the
                // selected option; this is what reveals the clear ("×") button.
                comboEl.classList.add('usa-combo-box--pristine');
            } else {
                // Mirror USWDS clear behavior so the placeholder shows again.
                input.value = '';
                comboEl.classList.remove('usa-combo-box--pristine');
                const key = comboEl.dataset.filterCombo;
                if (key && COMBO_PLACEHOLDERS[key]) {
                    input.setAttribute('placeholder', COMBO_PLACEHOLDERS[key]);
                }
            }
        }

        select.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // The floating "Feedback" launcher is the Zendesk Web Widget (loaded
    // globally from static.zdassets.com). Zendesk renders its launcher inside
    // an IFRAME in the host document; the clickable [aria-label="Feedback"]
    // lives *inside* that iframe (a separate document) so we can't select it
    // from here. Its z-index sits above our drawer, so we hide the whole widget
    // while a drawer/panel is open and restore it on close.

    // The launcher iframe in the host document (classic widget uses
    // id="launcher"; messaging widget uses a title attribute).
    function feedbackLauncherIframes() {
        return Array.from(
            document.querySelectorAll(
                'iframe#launcher, ' +
                'iframe[title*="messaging" i], ' +
                'iframe[title*="widget" i], ' +
                'iframe[title*="feedback" i]'
            )
        );
    }

    function setFeedbackButtonHidden(hidden) {
        // Prefer the official Zendesk API when present; it cleanly hides/shows
        // the launcher for both the classic Web Widget and the newer messaging
        // widget. We don't know which is loaded, so try both (one no-ops).
        const zE = window.zE;
        if (typeof zE === 'function') {
            try { zE('messenger', hidden ? 'hide' : 'show'); } catch (e) { /* not messaging */ }
            try { zE('webWidget', hidden ? 'hide' : 'show'); } catch (e) { /* not classic */ }
        }
        // Fallback / belt-and-suspenders: hide the launcher iframe directly in
        // case the API is unavailable or a no-op for this widget version.
        feedbackLauncherIframes().forEach((el) => {
            el.style.setProperty('display', hidden ? 'none' : '', hidden ? 'important' : '');
        });
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
        const controller = autoSubmitController();
        if (controller && typeof controller.request === 'function' && controller.form) {
            controller.request({ force: true });
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

                // Single-select combo box facets (organization, publisher):
                // selecting an option (or a popular quick-pick) auto-applies.
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

        // Mobile-only "Filters" toggle: collapses/expands the wrapped facet bar.
        // The bar is hidden by default on small screens (CSS); this flips the
        // .filter-bar--expanded class and the button's aria-expanded state. On
        // wider screens the button is display:none, so the bar is always shown.
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
            setFeedbackButtonHidden(true);

            // The backdrop is part of the mobile bottom-drawer layout only; on
            // wider screens outside-clicks are handled by the document listener.
            if (this.backdrop && isMobile()) {
                this.backdrop.hidden = false;
                document.body.classList.add('filter-bar-open');
            }

            // Reset any inline positioning before measuring.
            facet.panel.style.left = '';
            facet.panel.style.right = '';
            if (!isMobile()) {
                this.positionPanel(facet);
            }

            if (facet.key === 'geography' && window.dataGovGeographyAutocomplete) {
                window.dataGovGeographyAutocomplete.onFacetOpened();
            }

            // Move focus to the first interactive element for keyboard users.
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
            setFeedbackButtonHidden(false);

            if (!options.skipDeferReset) {
                setDeferred(false);
            }
        },

        // On wide screens, shift the panel left if it would overflow the
        // right edge of the viewport (keeps tablet dropdowns on-screen).
        positionPanel(facet) {
            const panel = facet.panel;
            const rect = panel.getBoundingClientRect();
            const viewportWidth = document.documentElement.clientWidth;
            if (rect.right > viewportWidth - VIEWPORT_MARGIN) {
                panel.style.left = 'auto';
                panel.style.right = '0';
            }
        },

        // Clear is only offered on deferred (multi-select) facets: Keywords
        // and Organization Type. Single-select combo facets clear by choosing
        // the blank option instead.
        clearFacet(facet) {
            const panel = facet.panel;
            // Native inputs: uncheck checkboxes, reset radios to their default.
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

            // Single-select combo box facets (organization, publisher): reset
            // the underlying <select> so Clear empties the staged selection.
            const comboEl = panel.querySelector('.usa-combo-box');
            const comboSelect = comboEl ? comboEl.querySelector('select') : null;
            if (comboSelect && comboSelect.value !== '') {
                setComboValue(comboSelect, '');
            }

            // Keyword chips live in their own autocomplete widget.
            if (facet.key === 'keywords' && window.dataGovKeywordAutocomplete) {
                window.dataGovKeywordAutocomplete.clearAll();
            }

            // Geography selection lives in JS (selectedGeometry + the map), not
            // native inputs, so clear it through its controller without
            // submitting — the Clear handler submits once afterward.
            if (facet.key === 'geography' && window.dataGovGeographyAutocomplete) {
                window.dataGovGeographyAutocomplete.clearStagedSelection();
            }
        },

        // Single-select combo box facets (organization, publisher). When the
        // facet is deferred, changing the <select> (typeahead, list pick, or
        // popular quick-pick) only stages the value — the Apply footer submits.
        // Non-deferred facets auto-submit on change. USWDS owns the enhanced
        // text input; we only need the underlying <select>.
        setupComboFacet(facet) {
            const comboEl = facet.panel.querySelector('.usa-combo-box');
            const select = comboEl ? comboEl.querySelector('select') : null;
            if (!select) {
                return;
            }

            applyComboPlaceholder(comboEl, facet.key);

            // The initial selection is seeded by USWDS from the wrapper's
            // data-default-value attribute (set server-side), which also makes
            // the clear ("×") button appear correctly on load.

            // Deferred combo facets just stage the selection; the Apply footer
            // submits. Non-deferred facets auto-submit immediately on change.
            if (!facet.deferred) {
                select.addEventListener('change', () => {
                    this.close({ skipDeferReset: true });
                    submitFilters();
                });

                // USWDS's clear ("×") button resets the <select> value but does
                // NOT fire a change event, so apply the cleared state explicitly.
                const clearInput = comboEl.querySelector('.usa-combo-box__clear-input');
                if (clearInput) {
                    clearInput.addEventListener('click', () => {
                        // Let USWDS clear the value first, then submit the empty filter.
                        window.setTimeout(() => {
                            this.close({ skipDeferReset: true });
                            submitFilters();
                        }, 0);
                    });
                }
            }

            // Popular quick-picks set the select value; for deferred facets this
            // just stages the value, for non-deferred it triggers the submit above.
            const group = facet.el.querySelector('#suggested-' + comboSuggestionGroup(facet.key));
            if (group) {
                group.querySelectorAll('[data-org-slug], [data-publisher-name]').forEach((btn) => {
                    btn.addEventListener('click', () => {
                        const value = btn.dataset.orgSlug || btn.dataset.publisherName || '';
                        setComboValue(select, value);
                    });
                });
            }
        },

        // Sort lives in the results header and re-runs the search immediately,
        // preserving the active filters carried by the main search form.
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
