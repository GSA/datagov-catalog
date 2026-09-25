(function() {
  'use strict';

  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initContactWidget);
  } else {
    initContactWidget();
  }

  function initContactWidget() {
    const button = document.getElementById('contact-widget-button');
    const panel = document.getElementById('contact-widget-panel');
    const closeButton = document.getElementById('contact-widget-close');
    const backButton = document.getElementById('contact-widget-back');
    const menuScreen = document.getElementById('widget-menu');
    const menuItems = document.querySelectorAll('.contact-widget__menu-item');

    if (!button || !panel || !closeButton || !backButton || !menuScreen) {
      return;
    }

    let currentScreen = 'menu';
    const screens = {
      menu: menuScreen,
      default: document.getElementById('widget-form-default'),
      feedback: document.getElementById('widget-form-feedback'),
      usagov: document.getElementById('widget-form-usagov')
    };

    // Open panel
    button.addEventListener('click', function() {
      openPanel();
    });

    // Close panel
    closeButton.addEventListener('click', function() {
      closePanel();
    });

    // Back button
    backButton.addEventListener('click', function() {
      showScreen('menu');
    });

    // Menu item clicks
    menuItems.forEach(function(item) {
      item.addEventListener('click', function() {
        const formType = this.getAttribute('data-form');
        showScreen(formType);
      });
    });

    // File upload handling
    setupFileUpload('default');
    setupFileUpload('feedback');
    setupFileUpload('usagov');

    // Close on escape key
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && panel.getAttribute('aria-hidden') === 'false') {
        closePanel();
      }
    });

    // Close when clicking outside
    panel.addEventListener('click', function(e) {
      if (e.target === panel) {
        closePanel();
      }
    });

    // If there are flash messages, auto-open the panel
    const alerts = panel.querySelectorAll('.usa-alert');
    if (alerts.length > 0) {
      setTimeout(function() {
        openPanel();
      }, 500);
    }

    function openPanel() {
      button.setAttribute('aria-expanded', 'true');
      panel.setAttribute('aria-hidden', 'false');

      // Show menu by default
      showScreen('menu');

      // Focus first interactive element
      setTimeout(function() {
        const firstInteractive = panel.querySelector('button:not([aria-label="Close contact form"]), input, textarea');
        if (firstInteractive) {
          firstInteractive.focus();
        }
      }, 100);
    }

    function closePanel() {
      button.setAttribute('aria-expanded', 'false');
      panel.setAttribute('aria-hidden', 'true');

      // Reset to menu after closing
      setTimeout(function() {
        showScreen('menu');
      }, 300);

      // Return focus to button
      button.focus();
    }

    function showScreen(screenName) {
      currentScreen = screenName;

      // Hide all screens
      Object.values(screens).forEach(function(screen) {
        if (screen) {
          screen.style.display = 'none';
        }
      });

      // Show requested screen
      if (screens[screenName]) {
        screens[screenName].style.display = 'block';
      }

      // Show/hide back button
      if (screenName === 'menu') {
        backButton.style.display = 'none';
      } else {
        backButton.style.display = 'flex';
      }

      // Focus first input if on a form
      if (screenName !== 'menu') {
        setTimeout(function() {
          const firstInput = screens[screenName].querySelector('input[type="text"]');
          if (firstInput) {
            firstInput.focus();
          }
        }, 100);
      }
    }

    function setupFileUpload(formType) {
      const fileInput = document.getElementById(formType + '-attachments');
      const fileList = document.getElementById(formType + '-file-list');

      if (!fileInput || !fileList) {
        return;
      }

      const MAX_FILES = 5;
      let selectedFiles = [];

      fileInput.addEventListener('change', function(e) {
        const newFiles = Array.from(e.target.files);

        // Check if adding these files would exceed the limit
        if (selectedFiles.length + newFiles.length > MAX_FILES) {
          alert('You can only upload up to ' + MAX_FILES + ' files.');
          fileInput.value = '';
          return;
        }

        // Add new files to the selected files array
        selectedFiles = selectedFiles.concat(newFiles);

        // Clear the input to allow re-selection
        fileInput.value = '';

        // Update the display
        updateFileList();
      });

      function updateFileList() {
        fileList.innerHTML = '';

        selectedFiles.forEach(function(file, index) {
          const fileItem = document.createElement('div');
          fileItem.className = 'contact-widget__file-item';

          const fileName = document.createElement('span');
          fileName.className = 'contact-widget__file-name';
          fileName.textContent = file.name;

          const removeButton = document.createElement('button');
          removeButton.type = 'button';
          removeButton.className = 'contact-widget__file-remove';
          removeButton.innerHTML = '&times;';
          removeButton.setAttribute('aria-label', 'Remove ' + file.name);
          removeButton.addEventListener('click', function() {
            removeFile(index);
          });

          fileItem.appendChild(fileName);
          fileItem.appendChild(removeButton);
          fileList.appendChild(fileItem);
        });

        // Update the actual file input with selected files
        updateFileInput();
      }

      function removeFile(index) {
        selectedFiles.splice(index, 1);
        updateFileList();
      }

      function updateFileInput() {
        // Create a new DataTransfer object to hold the files
        const dataTransfer = new DataTransfer();
        selectedFiles.forEach(function(file) {
          dataTransfer.items.add(file);
        });
        fileInput.files = dataTransfer.files;
      }
    }
  }
})();
