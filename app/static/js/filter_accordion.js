(function (window, document) {
    const storageKey = 'datagov.filterAccordionState';

    function readState() {
        if (!window.sessionStorage) {
            return {};
        }

        try {
            const raw = window.sessionStorage.getItem(storageKey);
            return raw ? JSON.parse(raw) : {};
        } catch (_err) {
            return {};
        }
    }

    function writeState(state) {
        if (!window.sessionStorage) {
            return;
        }

        try {
            window.sessionStorage.setItem(storageKey, JSON.stringify(state));
        } catch (_err) {
            // Ignore storage errors (privacy mode, quota, disabled storage).
        }
    }

    function setExpanded(button, content, expanded) {
        button.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        content.hidden = !expanded;
    }

    function getSectionParts(section) {
        const sectionId = section.dataset.filterSection;
        const button = section.querySelector('.usa-accordion__button');
        const content = section.querySelector('.usa-accordion__content');
        if (!button || !content || !sectionId) {
            return null;
        }

        return { sectionId, button, content };
    }

    function isSectionExpanded(parts) {
        return parts.button.getAttribute('aria-expanded') === 'true';
    }

    function areAllExpanded(sections) {
        return Array.from(sections).every((section) => {
            const parts = getSectionParts(section);
            return parts && isSectionExpanded(parts);
        });
    }

    function updateToggleAllButtons(toggleButtons, sections) {
        if (!toggleButtons.length || !sections.length) {
            return;
        }

        const allExpanded = areAllExpanded(sections);
        const label = allExpanded ? 'Collapse all' : 'Expand all';
        const ariaLabel = allExpanded ? 'Collapse all filters' : 'Expand all filters';

        toggleButtons.forEach((toggleButton) => {
            toggleButton.textContent = label;
            toggleButton.setAttribute('data-expanded', allExpanded ? 'true' : 'false');
            toggleButton.setAttribute('aria-label', ariaLabel);
        });
    }

    function persistSectionStates(sections) {
        const state = readState();
        sections.forEach((section) => {
            const parts = getSectionParts(section);
            if (!parts) {
                return;
            }
            state[parts.sectionId] = isSectionExpanded(parts);
        });
        writeState(state);
    }

    function setAllExpanded(sections, expanded) {
        sections.forEach((section) => {
            const parts = getSectionParts(section);
            if (!parts) {
                return;
            }
            setExpanded(parts.button, parts.content, expanded);
        });
        persistSectionStates(sections);
    }

    function initFilterAccordions() {
        const form = document.getElementById('filter-form');
        if (!form || form.dataset.filterAccordionInit === 'true') {
            return;
        }
        form.dataset.filterAccordionInit = 'true';

        const sections = form.querySelectorAll('[data-filter-section]');
        if (!sections.length) {
            return;
        }

        const toggleButtons = Array.from(
            document.querySelectorAll('[data-filter-toggle-all]')
        );
        const savedState = readState();

        sections.forEach((section) => {
            const parts = getSectionParts(section);
            if (!parts) {
                return;
            }

            const isActive = section.dataset.filterActive === 'true';
            const savedExpanded = savedState[parts.sectionId];

            if (savedExpanded === false) {
                setExpanded(parts.button, parts.content, false);
            } else if (savedExpanded === true) {
                setExpanded(parts.button, parts.content, true);
            } else if (isActive) {
                setExpanded(parts.button, parts.content, true);
            } else {
                // Server renders all sections expanded for no-JS; collapse inactive by default.
                setExpanded(parts.button, parts.content, false);
            }

            parts.button.addEventListener('click', () => {
                window.requestAnimationFrame(() => {
                    persistSectionStates(sections);
                    updateToggleAllButtons(toggleButtons, sections);
                });
            });
        });

        form.addEventListener('submit', () => {
            persistSectionStates(sections);
        });

        updateToggleAllButtons(toggleButtons, sections);

        toggleButtons.forEach((toggleButton) => {
            toggleButton.addEventListener('click', () => {
                const expandAll = !areAllExpanded(sections);
                setAllExpanded(sections, expandAll);
                updateToggleAllButtons(toggleButtons, sections);
            });
        });
    }

    if (document.getElementById('filter-form')) {
        initFilterAccordions();
    } else {
        document.addEventListener('DOMContentLoaded', initFilterAccordions);
    }
})(window, document);
