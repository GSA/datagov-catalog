/**
 * Hide third-party page launchers (e.g. Zendesk) while modal UI is open.
 */
(function (window, document) {
    function launcherIframes() {
        return Array.from(
            document.querySelectorAll(
                'iframe#launcher, ' +
                'iframe[title*="messaging" i], ' +
                'iframe[title*="widget" i], ' +
                'iframe[title*="feedback" i]'
            )
        );
    }

    function setHidden(hidden) {
        const zE = window.zE;
        if (typeof zE === 'function') {
            try {
                zE('messenger', hidden ? 'hide' : 'show');
            } catch (e) {
                /* not messaging */
            }
            try {
                zE('webWidget', hidden ? 'hide' : 'show');
            } catch (e) {
                /* not classic */
            }
        }
        launcherIframes().forEach((el) => {
            el.style.setProperty('display', hidden ? 'none' : '', hidden ? 'important' : '');
        });
    }

    window.dataGovThirdPartyLauncher = {
        setHidden,
    };
})(window, document);
