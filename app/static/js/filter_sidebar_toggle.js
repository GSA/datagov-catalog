(function (window, document) {
    const MOBILE_MEDIA = '(max-width: 63.99em)';

    function isMobileViewport() {
        return window.matchMedia(MOBILE_MEDIA).matches;
    }

    function getElements() {
        return {
            toggleButton: document.getElementById('filter-mobile-toggle'),
            panel: document.getElementById('filter-sidebar-panel'),
            label: document.querySelector('.filter-mobile-trigger__label'),
        };
    }

    function updateToggleLabel(elements, expanded) {
        if (elements.label) {
            elements.label.textContent = expanded ? 'Hide filters' : 'Show filters';
        }
    }

    function setPanelExpanded(elements, expanded) {
        if (!elements.panel) {
            return;
        }

        if (!isMobileViewport()) {
            elements.panel.hidden = false;
            if (elements.toggleButton) {
                elements.toggleButton.setAttribute('aria-expanded', 'true');
            }
            return;
        }

        elements.panel.hidden = !expanded;
        if (elements.toggleButton) {
            elements.toggleButton.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        }
        updateToggleLabel(elements, expanded);
    }

    function initFilterSidebarToggle() {
        const elements = getElements();
        if (!elements.panel || !elements.toggleButton) {
            return;
        }

        setPanelExpanded(elements, false);

        elements.toggleButton.addEventListener('click', () => {
            setPanelExpanded(elements, elements.panel.hidden);
        });

        window.matchMedia(MOBILE_MEDIA).addEventListener('change', (event) => {
            if (!event.matches) {
                setPanelExpanded(elements, true);
                return;
            }
            setPanelExpanded(elements, false);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFilterSidebarToggle);
    } else {
        initFilterSidebarToggle();
    }
})(window, document);
