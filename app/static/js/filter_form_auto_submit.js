(function (window, document) {
    const autoSubmit = {
        form: null,
        init(form) {
            this.form = form || null;
        },
        request() {
            if (!this.form) {
                return;
            }

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
