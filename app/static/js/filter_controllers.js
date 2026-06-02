/**
 * Registry for filter facet widgets that manage staged state outside native inputs.
 */
(function (window) {
    const controllers = {};

    window.dataGovFilterControllers = {
        register(key, api) {
            if (!key) {
                return;
            }
            controllers[key] = api || null;
        },
        clearStaged(key) {
            const api = controllers[key];
            if (api && typeof api.clearStaged === 'function') {
                api.clearStaged();
            }
        },
    };
})(window);
