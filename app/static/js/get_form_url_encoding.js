(function (window, document) {
  function submitGetForm(event) {
    const form = event.target;

    if (!form.matches('form[method="get" i]') || event.defaultPrevented) {
      return;
    }

    event.preventDefault();

    const formData = new FormData(form);
    const submitter = event.submitter;

    if (submitter && submitter.name) {
      formData.append(submitter.name, submitter.value);
    }

    const url = new URL(
      form.action || window.location.href,
      window.location.href,
    );

    // Use %20 instead of + for spaces.
    url.search = new URLSearchParams(formData).toString().replace(/\+/g, "%20");

    window.location.assign(url.href);
  }

  // Submit events bubble from the form to document.
  // This runs after the form's own submit handlers.
  document.addEventListener("submit", submitGetForm);
})(window, document);
