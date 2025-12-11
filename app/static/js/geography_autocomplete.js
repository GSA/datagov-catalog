/* global L */
class GeographyAutocomplete {
    constructor(options) {
        this.inputId = options.inputId;
        this.suggestionsId = options.suggestionsId;
        this.apiEndpoint = options.apiEndpoint || '/api/location';
        this.formId = options.formId;
        this.mainSearchFormId = options.mainSearchFormId;
        this.debounceDelay = options.debounceDelay || 300;

        this.input = document.getElementById(this.inputId);
        this.suggestionsContainer = document.getElementById(this.suggestionsId);
        this.form = document.getElementById(this.formId);
        this.mainSearchForm = document.getElementById(this.mainSearchFormId); // NEW

        this.selectedGeometry = null;
        this.geoLayer = null;
        this.allGeographies = [];
        this.debounceTimer = null;
        this.currentFocusIndex = -1;
        this.map = null;

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

        // Close suggestions when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });

        // Sync selection to hidden inputs on form submit
        if (this.form) {
            this.form.addEventListener('submit', () => this.syncHiddenInputs());
        }

        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', (e) => {
                this.syncHiddenInputsToMainSearch();
            });
        }
    }

    loadExistingGeography() {
        // Load geography from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const existingGeometry = urlParams.get('spatial_geometry');
        if (existingGeometry) {
            // URL-encoded parameter is a string of a GeoJSON object
            this.selectedGeometry = JSON.parse(decodeURI(existingGeometry))
            this.displayGeometry(this.selectedGeometry);
            this.showClearButton();
        } else {
          this.displayNoGeometry();
        }
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

    // handle the click of the clear button
    clearClicked() {
      this.selectedGeometry = null;
      this.displayNoGeometry();
      if (this.map) this.map.removeLayer(this.geoLayer);

      // now remove the clear button
      const labelDiv = document.getElementById('geography-input-label');
      if (!labelDiv) return;  // Can't find where it is
      const clearButton = labelDiv.querySelector('#geography-clear-button');
      if (!clearButton) return;
      labelDiv.removeChild(clearButton);
    }

    _createMap() {
      // create a map and store it on this.map
      if (this.map) return;  // don't create the map if it already exists
      var el = document.getElementById('geography-map');
      if (!el) return;
      if (typeof L === 'undefined') return;
      var map = L.map(el, { zoomControl: true, attributionControl: false });
      var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19
      }).addTo(map);
      this.map = map;
    }

    displayGeometry(geometry) {
        // Show this GeoJSON object on our map tile
      this._createMap();  // map object is in this.map
      if (!this.map) {
        console.error('Could not construct map');
        return;
      }
      this.geoLayer = L.geoJSON(geometry, {
        style: function () {
          return { color: '#005ea2', weight: 2, fillOpacity: 0.05 };
        },
        pointToLayer: function (_feature, latlng) {
          return L.marker(latlng);
        }
      }).addTo(this.map);

      var geoBounds = this.geoLayer.getBounds();
      if (geoBounds.isValid()) {
        if (geoBounds.getSouthWest().equals(geoBounds.getNorthEast())) {
          this.map.setView(geoBounds.getSouthWest(), 8);
        } else {
          this.map.fitBounds(geoBounds.pad(0.1));
        }
      }
    }

    displayNoGeometry() {
      this._createMap();
      if (!this.map) {
        console.error('Could not construct map');
        return;
      }
      this.map.setView([44.967243, -103.77155], 2);
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
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            if (this.currentFocusIndex >= 0 && suggestions[this.currentFocusIndex]) {
                e.preventDefault();
                const loc = suggestions[this.currentFocusIndex].location_data;
                this.selectGeography(loc);
                this.input.value = '';
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
                this.input.value = '';
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
      try {
        const response = await fetch(`${this.apiEndpoint}/${location_id}`);
        const data = await response.json();
        // data.geometry is a string of the GeoJSON geometry of that location
        this.selectedGeometry = JSON.parse(data.geometry);
        this.showClearButton();
        this.displayGeometry(this.selectedGeometry);
      } catch (error) {
        console.error('Error loading location data:', error);
      }
    }

    // Sync geometry to hidden inputs in the filter form
    syncHiddenInputs() {
        // Remove existing geometry hidden input from filter form
        const existingInputs = this.form.querySelectorAll('input[name="spatial_geometry"]');
        existingInputs.forEach(input => input.remove());

        // add hidden input for spatial_geometry
        if (this.selectedGeometry) {
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = 'spatial_geometry';
          // URI-encoding should be handled by form submission
          input.value = JSON.stringify(this.selectedGeometry);
          this.form.appendChild(input);
        }
    }

    // Sync geometry to hidden inputs in the main search form
    syncHiddenInputsToMainSearch() {
        if (!this.mainSearchForm) return;

        // Remove existing keyword hidden inputs from main search form
        const existingInputs = this.mainSearchForm.querySelectorAll('input[name="spatial_geometry"][type="hidden"]');
        existingInputs.forEach(input => input.remove());

        // Add hidden input for spatial geometry
        if (this.selectedGeometry) {
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = 'spatial_geometry';
          // URI-encoding should be handled by form submission
          input.value = JSON.stringify(this.selectedGeometry);
          this.mainSearchForm.appendChild(input);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const geographyAutocomplete = new GeographyAutocomplete({
        inputId: 'geography-input',
        suggestionsId: 'geography-suggestions',
        formId: 'filter-form',
        mainSearchFormId: 'main-search-form', // NEW: main search form ID
        apiEndpoint: '/api/location',
        debounceDelay: 300
    });
});
