/* Geography filter typeahead; map UI lives in geography_map_mixin.js */
/* global L */

class GeographyAutocomplete {
    constructor(options) {
        this.mapPanelNextStateStorageKey = 'datagov.geographyMapExpanded.nextState';
        this.inputId = options.inputId;
        this.suggestionsId = options.suggestionsId;
        this.apiEndpoint = options.apiEndpoint || '/api/location';
        this.formId = options.formId;
        this.mainSearchFormId = options.mainSearchFormId;
        this.debounceDelay = options.debounceDelay || 300;

        this.input = document.getElementById(this.inputId);
        this.inputWrap = this.input
          ? this.input.closest('.geography-input-wrap')
          : null;
        this.inputClearButton = document.getElementById('geography-input-clear');
        this.suggestionsContainer = document.getElementById(this.suggestionsId);
        this.form = document.getElementById(this.formId);
        this.mainSearchForm = document.getElementById(this.mainSearchFormId);

        this.selectedGeometry = null;
        this.spatialLabel = '';
        this.geoLayer = null;
        this.allGeographies = [];
        this.debounceTimer = null;
        this.currentFocusIndex = -1;
        this.map = null;
        this.mapHandlersInitialized = false;
        this.drawControl = null;
        this.mapPanelCloseButton = null;
        this.mapPanelToggleButton = null;
        this.mapPanelElement = null;
        this.mapPanelMapContainer = null;
        this.mapPanelMap = null;
        this.mapPanelGeoLayer = null;
        this.searchResultGeometries = window.dataGovGeographyUtils.loadSearchResultGeometries();
        this.mapPanelResultsLayer = null;
        this.mapPanelApplyButton = null;
        this.drawButton = null;
        this.isDrawing = false;
        this.drawStartLatLng = null;
        this.drawRect = null;
        this.pendingGeometry = null;
        this.suppressResultLayerUntilReload = false;
        this.spatialWithin = true;
        this.pendingSpatialWithin = null;
        this.spatialWithinRadios = null;
        this.boundDrawStart = this.onDrawStart.bind(this);
        this.boundDrawMove = this.onDrawMove.bind(this);
        this.boundDrawEnd = this.onDrawEnd.bind(this);
        this.usePointerEvents =
          typeof window !== 'undefined' &&
          (window.PointerEvent || window.MSPointerEvent);
        this.activePointerId = null;
        this.drawContainer = null;
        this.prevTouchAction = null;
        this.prevMsTouchAction = null;

        if (!this.input || !this.suggestionsContainer) {
            console.error('GeographyAutocomplete: Required elements not found');
            return;
        }

        this.init();
    }

    init() {
        // Load any existing keywords from URL parameters
        this.loadExistingGeography();

        // Initialize suggested keywords click handlers
        this.initSuggestedGeography();

        // Event listeners
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeyDown(e));
        this.input.addEventListener('focus', () => this.showSuggestions());
        this.initInputClearButton();

        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            const inInputArea =
              (this.inputWrap && this.inputWrap.contains(e.target)) ||
              this.input.contains(e.target);
            if (!inInputArea && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });

        // Sync selection to hidden inputs on form submit and persist the
        // expanded map panel's open state so it can be restored after reload.
        if (this.form) {
            this.form.addEventListener('submit', () => {
                this.syncHiddenInputs();
                this.persistCurrentMapPanelStateForNextLoad();
            });
        }

        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', () => {
                this.syncHiddenInputsToMainSearch();
                this.persistCurrentMapPanelStateForNextLoad();
            });
        }

        this.initMapPanel();
    }

    loadExistingGeography() {
        // Load geography from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const existingGeometry = urlParams.get('spatial_geometry');
        const existingLabel = urlParams.get('spatial_label');
        this.spatialWithin = window.dataGovGeographyUtils.parseSpatialWithinParam(
          urlParams.get('spatial_within')
        );
        this.pendingSpatialWithin = null;
        if (existingGeometry) {
            // URL-encoded parameter is a string of a GeoJSON object
            this.selectedGeometry = JSON.parse(decodeURI(existingGeometry));
            this.spatialLabel = existingLabel ? existingLabel.trim() : '';
            if (this.spatialLabel) {
              this.input.value = this.spatialLabel;
            }
            this.showClearButton();
            // Defer map render until the facet panel is visible (Leaflet needs
            // a sized container for fitBounds to work).
        } else {
          this.selectedGeometry = null;
          this.spatialLabel = '';
        }
        this.updateInputClearButtonVisibility();
    }

    initInputClearButton() {
        if (!this.inputClearButton) return;
        this.inputClearButton.addEventListener('click', (e) => {
            e.preventDefault();
            this.clearInputText();
        });
        this.updateInputClearButtonVisibility();
    }

    updateInputClearButtonVisibility() {
        if (!this.inputClearButton || !this.input) return;
        const hasText = this.input.value.trim().length > 0;
        this.inputClearButton.classList.toggle(
          'geography-input__clear--visible',
          hasText
        );
        this.inputClearButton.tabIndex = hasText ? 0 : -1;
    }

    // Clear only the typeahead text so the user can search again; geometry/map
    // stay staged until Apply, Clear, or a new selection replaces them.
    clearInputText() {
        if (!this.input) return;
        this.input.value = '';
        this.updateInputClearButtonVisibility();
        this.hideSuggestions();
        this.input.focus({ preventScroll: true });
    }

    syncSpatialWithinRadios() {
      if (!this.spatialWithinRadios || !this.spatialWithinRadios.length) return;
      const value =
        this.pendingSpatialWithin !== null
          ? this.pendingSpatialWithin
          : this.spatialWithin;
      const targetValue = value ? 'true' : 'false';
      this.spatialWithinRadios.forEach((radio) => {
        radio.checked = radio.value === targetValue;
      });
    }

    onSpatialWithinChange(event) {
      if (!event || !event.target) return;
      const nextWithin = event.target.value === 'true';
      this.pendingSpatialWithin =
        nextWithin === this.spatialWithin ? null : nextWithin;
      this.updateApplyButtonState();
    }

    _isWithinRelationActive() {
      return this.spatialWithin;
    }

    showClearButton() {
      // show a clear button to stop filtering
      const clearButton = document.getElementById('geography-clear-button');
      // button already exists
      if (clearButton) return;
      // make the button
      const labelDiv = document.getElementById('geography-input-label');
      if (!labelDiv) return;  // Can't find where to put it
      const button = document.createElement('button');
      button.id = 'geography-clear-button';
      button.className = 'tag-link tag-link--suggested';
      button.innerHTML = 'Clear';
      button.addEventListener('click', () => {
          this.clearClicked();
      });
      labelDiv.appendChild(button);
    }

    // handle the click of the inline clear button. Geography is a deferred
    // facet, so this only stages the empty state; the facet's Apply footer (or
    // the footer Clear, via clearStagedSelection) submits it.
    clearClicked() {
      this.clearStagedSelection();
    }

    // Reset the staged geography selection (geometry, pending box, relation)
    // and the map, without submitting. Used by the inline clear button and the
    // facet footer's Clear action (which submits once afterward itself).
    clearStagedSelection() {
      this.selectedGeometry = null;
      this.spatialLabel = '';
      this.pendingSpatialWithin = null;
      this.input.value = '';
      this.updateInputClearButtonVisibility();
      this.disableDrawMode();
      this.displayNoGeometry();
      this.syncSpatialWithinRadios();
      if (this.map) this.map.removeLayer(this.geoLayer);

      // now remove the inline clear button
      const labelDiv = document.getElementById('geography-input-label');
      if (!labelDiv) return;  // Can't find where it is
      const clearButton = labelDiv.querySelector('#geography-clear-button');
      if (!clearButton) return;
      labelDiv.removeChild(clearButton);
    }
    initSuggestedGeography() {
        // Add click handlers to suggested keyword buttons
        if (!this.suggestionsContainer) return;

        const suggestedButtons = this.suggestionsContainer.querySelectorAll('.tag-link--suggested');
        suggestedButtons.forEach(button => {
            button.addEventListener('click', () => {
                const loc = button.location_data;
                if (loc) {
                    this.selectGeography(loc);
                    // Hide suggested keywords container after selection
                    this.hideSuggestions();
                }
            });
        });
    }

    hideSuggestions() {
        this.suggestionsContainer.classList.remove('keyword-suggestions--visible');
        this.currentFocusIndex = -1;
    }

    showSuggestions() {
       this.suggestionsContainer.classList.add('keyword-suggestions--visible');
    }

    handleInput(e) {
        this.updateInputClearButtonVisibility();
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            const query = e.target.value.trim().toLowerCase();
            // only show suggestions when we have 3 or more search characters
            if (query.length < 2) {
                this.hideSuggestions();
            } else {
                this.filterAndShowSuggestions(query);
            }
        }, this.debounceDelay);
    }

    handleKeyDown(e) {
        const suggestions = this.suggestionsContainer.querySelectorAll('.keyword-suggestion');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.currentFocusIndex = Math.min(this.currentFocusIndex + 1, suggestions.length - 1);
            this.updateSuggestionFocus(suggestions);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.currentFocusIndex = Math.max(this.currentFocusIndex - 1, 0);
            this.updateSuggestionFocus(suggestions);
        } else if (e.key === 'Enter') {
            // Enter applies the filter: stage the focused (or first) suggestion,
            // then submit even though geography is a deferred facet. Always
            // prevent the default so a bare Enter never triggers a native submit.
            e.preventDefault();
            let node = null;
            if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
                node = suggestions[this.currentFocusIndex];
            } else if (suggestions.length > 0) {
                node = suggestions[0];
            }
            if (node && node.location_data) {
                this.selectGeography(node.location_data).then(() => {
                    window.dataGovFilterSubmit.request(this.form, { force: true });
                });
                this.hideSuggestions();
            }
        } else if (e.key === 'Tab') {
            // Tab stages the focused suggestion without submitting.
            if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
                e.preventDefault();
                const loc = suggestions[this.currentFocusIndex].location_data;
                this.selectGeography(loc);
                this.hideSuggestions();
            }
        } else if (e.key === 'Escape') {
            this.hideSuggestions();
        }
    }

    updateSuggestionFocus(suggestions) {
        suggestions.forEach((item, index) => {
            if (index === this.currentFocusIndex) {
                item.classList.add('keyword-suggestion--focused');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('keyword-suggestion--focused');
            }
        });
    }

    async filterAndShowSuggestions(query) {
        // Filter keywords that match the query
        // TODO: this calls the location search API every time, we could
        // try some caching to save on calls
        query = query.toLowerCase();
        const response = await fetch(`${this.apiEndpoint}s/search?q=${query}&size=10`);
        const filtered = await response.json();

        if (filtered.locations.length > 0) {
            this.renderSuggestions(filtered.locations);
            this.showSuggestions();
        } else {
            this.hideSuggestions();
        }
    }

    renderSuggestions(locations) {
        this.suggestionsContainer.innerHTML = '';
        this.currentFocusIndex = -1;

        locations.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'keyword-suggestion';
            div.location_data = item;
            div.innerHTML = `
                <span class="keyword-suggestion__text">${this.highlightMatch(item.display_name, this.input.value)}</span>
            `;

            div.addEventListener('click', () => {
                this.selectGeography(item);
                this.hideSuggestions();
            });

            this.suggestionsContainer.appendChild(div);
        });
    }

    highlightMatch(text, query) {
        const index = text.toLowerCase().indexOf(query.toLowerCase());
        if (index === -1) return text;

        const before = text.substring(0, index);
        const match = text.substring(index, index + query.length);
        const after = text.substring(index + query.length);

        return `${before}<strong>${match}</strong>${after}`;
    }

    async selectGeography(location_data) {
      // select this location, get the geometry and show it on the map
      var location_id = location_data.id;
      const displayName = location_data.display_name || '';
      try {
        const response = await fetch(`${this.apiEndpoint}/${location_id}`);
        const data = await response.json();
        // data.geometry is a string of the GeoJSON geometry of that location
        this.selectedGeometry = JSON.parse(data.geometry);
        this.spatialLabel = displayName;
        this.input.value = displayName;
        this.updateInputClearButtonVisibility();
        this.showClearButton();
        this.displayGeometry(this.selectedGeometry);
        // Geography is a deferred facet: stage the selection and let the
        // facet's Apply footer submit it.
      } catch (error) {
        console.error('Error loading location data:', error);
      }
    }

    _syncSpatialHiddenInputs(form) {
        if (!form) return;

        const existingGeometryInputs = form.querySelectorAll(
          'input[name="spatial_geometry"][type="hidden"]'
        );
        existingGeometryInputs.forEach(input => input.remove());

        const existingWithinInputs = form.querySelectorAll(
          'input[name="spatial_within"][type="hidden"]'
        );
        existingWithinInputs.forEach(input => input.remove());

        const existingLabelInputs = form.querySelectorAll(
          'input[name="spatial_label"][type="hidden"]'
        );
        existingLabelInputs.forEach(input => input.remove());

        if (this.selectedGeometry) {
          const geometryInput = document.createElement('input');
          geometryInput.type = 'hidden';
          geometryInput.name = 'spatial_geometry';
          // URI-encoding should be handled by form submission
          geometryInput.value = JSON.stringify(this.selectedGeometry);
          form.appendChild(geometryInput);

          const withinInput = document.createElement('input');
          withinInput.type = 'hidden';
          withinInput.name = 'spatial_within';
          withinInput.value = this.spatialWithin ? 'true' : 'false';
          form.appendChild(withinInput);

          if (this.spatialLabel) {
            const labelInput = document.createElement('input');
            labelInput.type = 'hidden';
            labelInput.name = 'spatial_label';
            labelInput.value = this.spatialLabel;
            form.appendChild(labelInput);
          }
        }
    }

    // Sync geometry to hidden inputs in the filter form
    syncHiddenInputs() {
        this._syncSpatialHiddenInputs(this.form);
    }

    // Sync geometry to hidden inputs in the main search form
    syncHiddenInputsToMainSearch() {
        this._syncSpatialHiddenInputs(this.mainSearchForm);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

Object.assign(GeographyAutocomplete.prototype, window.dataGovGeographyMapMixin);

document.addEventListener('DOMContentLoaded', () => {
    const geographyAutocomplete = new GeographyAutocomplete({
        inputId: 'geography-input',
        suggestionsId: 'geography-suggestions',
        formId: 'filter-form',
        mainSearchFormId: 'main-search-form',
        apiEndpoint: '/api/location',
        debounceDelay: 300,
    });
    window.dataGovGeographyAutocomplete = geographyAutocomplete;
    if (window.dataGovFilterControllers) {
        window.dataGovFilterControllers.register('geography', {
            clearStaged: () => geographyAutocomplete.clearStagedSelection(),
        });
    }
});

