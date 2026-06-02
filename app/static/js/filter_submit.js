/**
 * Submit the catalog filter form, respecting deferred facet staging.
 */
(function (window) {
    function requestFilterFormSubmit(form, options = {}) {
        const controller = window.dataGovFilterFormAutoSubmit;
        if (controller && typeof controller.request === 'function' && controller.form) {
            controller.request(options);
            return;
        }

        if (!form) {
            return;
        }

        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    window.dataGovFilterSubmit = {
        request: requestFilterFormSubmit,
    };
})(window);
