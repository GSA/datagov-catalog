const FEEDBACK_BUTTON_ID = "contact-btn";
const TOUCHPOINTS_FORM_ID = "fd986495";
const TOUCHPOINTS_SCRIPT_URL = `https://touchpoints.app.cloud.gov/touchpoints/${TOUCHPOINTS_FORM_ID}.js`;

function loadTouchpointsScript() {
  return new Promise((resolve, reject) => {
    if (window[`touchpointForm${TOUCHPOINTS_FORM_ID}`]) {
      resolve();
      return;
    }

    const existingScript = document.querySelector(
      `script[src="${TOUCHPOINTS_SCRIPT_URL}"]`
    );

    if (existingScript) {
      if (existingScript.dataset.loaded === "true") {
        resolve();
      } else {
        existingScript.addEventListener("load", () => resolve());
        existingScript.addEventListener("error", () => reject());
      }
      return;
    }

    const script = document.createElement("script");
    script.src = TOUCHPOINTS_SCRIPT_URL;
    script.async = true;
    script.defer = true;

    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    });

    script.addEventListener("error", () => reject());

    document.head.appendChild(script);
  });
}

function setFeedbackDatasetContext(buttonEl) {
  if (!buttonEl) {
    return;
  }

  const datasetIdentifier = buttonEl.getAttribute("data-dataset-identifier");
  if (!datasetIdentifier) {
    return;
  }

  const datasetField = document.getElementById("question_42229_answer_04");
  if (datasetField) {
    datasetField.value = datasetIdentifier;
  }

  const locationField = document.getElementById("fba_location_code");
  if (locationField) {
    locationField.value = datasetIdentifier;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const feedbackButton = document.getElementById(FEEDBACK_BUTTON_ID);
  if (!feedbackButton) {
    return;
  }

  document.addEventListener("onTouchpointsFormLoaded", () => {
    setFeedbackDatasetContext(feedbackButton);
  });

  document.addEventListener("onTouchpointsModalOpen", () => {
    setFeedbackDatasetContext(feedbackButton);
  });

  feedbackButton.addEventListener("click", () => {
    setFeedbackDatasetContext(feedbackButton);
  });

  loadTouchpointsScript().catch(() => {
    // eslint-disable-next-line no-console
    console.error("Failed to load Touchpoints feedback form script.");
  });
});
