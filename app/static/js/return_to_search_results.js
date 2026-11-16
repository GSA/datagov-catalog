(function () {
    const link = document.getElementById('return-to-search-results');
    // only show the link if there is a history.
    if (!link || !document.referrer || window.history.length <= 1) {
        return;
    }

    try {
        const previous = new URL(document.referrer);
        // only show the link if the previous page
        // - is on the same origin, and
        // - is from a dataset listing page (/ or /organization/<org-name>))
        if (previous.origin !== window.location.origin || !(
            previous.pathname === '/' ||
            /^\/organization\/[^/]+\/?$/.test(previous.pathname)
        )) {
            return;
        }
    } catch (_error) {
        return;
    }

    link.href = document.referrer;
    link.hidden = false;
    link.addEventListener('click', function (event) {
        event.preventDefault();
        window.history.go(-1);
    });
}());
