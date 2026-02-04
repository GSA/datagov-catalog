/* global L */
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
        this.mapHandlersInitialized = false;
        this.drawControl = null;
        this.modalTrigger = null;
        this.modalElement = null;
        this.modalMapContainer = null;
        this.modalMap = null;
        this.modalGeoLayer = null;
        this.modalApplyButton = null;
        this.drawButton = null;
        this.isDrawing = false;
        this.drawStartLatLng = null;
        this.drawRect = null;
        this.pendingGeometry = null;
        this.spatialWithin = true;
        this.pendingSpatialWithin = null;
        this.spatialWithinRadios = null;
        this.boundDrawStart = this.onDrawStart.bind(this);
        this.boundDrawMove = this.onDrawMove.bind(this);
        this.boundDrawEnd = this.onDrawEnd.bind(this);

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

        this.initModal();
        this.handlePostApplyScroll();
    }

    initModal() {
      this.modalTrigger = document.getElementById('geography-map-modal-trigger');
      this.modalElement = document.getElementById('geography-map-modal');
      this.modalMapContainer = document.getElementById('geography-map-modal-map');
      this.drawButton = document.getElementById('geography-modal-draw-toggle');
      this.modalApplyButton = document.getElementById('geography-modal-apply');
      this.spatialWithinRadios = this.modalElement
        ? this.modalElement.querySelectorAll('input[name="spatial_within"]')
        : null;

      if (this.drawButton) {
        this.drawButton.setAttribute('aria-pressed', 'false');
        this.drawButton.addEventListener('click', () => {
          this.toggleDrawMode();
        });
      }

      if (this.modalApplyButton) {
        this.modalApplyButton.addEventListener('click', () => {
          this.applyPendingGeometry();
        });
        this.updateApplyButtonState();
      }

      if (this.spatialWithinRadios && this.spatialWithinRadios.length) {
        this.spatialWithinRadios.forEach((radio) => {
          radio.addEventListener('change', (e) => {
            this.onSpatialWithinChange(e);
          });
        });
        this.syncSpatialWithinRadios();
      }

      if (this.modalElement) {
        this.modalElement.addEventListener('click', (e) => {
          if (e.target && e.target.closest('[data-close-modal]')) {
            this.disableDrawMode();
            if (!e.target.closest('#geography-modal-apply')) {
              this.pendingGeometry = null;
              this.pendingSpatialWithin = null;
              this.syncSpatialWithinRadios();
              this.updateApplyButtonState();
              this._syncModalMap();
            }
          }
        });
      }
    }

    parseSpatialWithinParam(value) {
      if (typeof value !== 'string') return true;
      const normalized = value.trim().toLowerCase();
      if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) return true;
      if (['false', '0', 'no', 'n', 'off'].includes(normalized)) return false;
      return true;
    }

    loadExistingGeography() {
        // Load geography from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const existingGeometry = urlParams.get('spatial_geometry');
        this.spatialWithin = this.parseSpatialWithinParam(
          urlParams.get('spatial_within')
        );
        this.pendingSpatialWithin = null;
        if (existingGeometry) {
            // URL-encoded parameter is a string of a GeoJSON object
            this.selectedGeometry = JSON.parse(decodeURI(existingGeometry))
            this.displayGeometry(this.selectedGeometry);
            this.showClearButton();
        } else {
          this.displayNoGeometry();
        }
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
      this.disableDrawMode();
      this.displayNoGeometry();
      if (this.map) this.map.removeLayer(this.geoLayer);

      // now remove the clear button
      const labelDiv = document.getElementById('geography-input-label');
      if (!labelDiv) return;  // Can't find where it is
      const clearButton = labelDiv.querySelector('#geography-clear-button');
      if (!clearButton) return;
      labelDiv.removeChild(clearButton);

      requestFilterFormSubmit(this.form);
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
      this._initMapHandlers();
    }

    _initMapHandlers() {
      if (!this.map || this.mapHandlersInitialized) return;
      this.mapHandlersInitialized = true;

      // Allow shift+drag box zoom to set a spatial filter box
      this.map.on('boxzoomend', (e) => {
        const bounds = e && e.boxZoomBounds ? e.boxZoomBounds : null;
        if (!bounds || !bounds.isValid()) return;
        this.applyBoundsSelection(bounds);
      });

      this._addDrawControl();
    }

    _addDrawControl() {
      if (!this.map || this.drawControl) return;
      const self = this;
      const DrawControl = L.Control.extend({
        onAdd: function () {
          const container = L.DomUtil.create('div', 'leaflet-bar geography-draw-control');
          const button = L.DomUtil.create('a', 'geography-draw-button', container);
          button.href = '#';
          button.title = 'Open a larger map to draw a box';
          button.setAttribute('role', 'button');
          button.setAttribute('aria-label', 'Open a larger map to draw a box');
          button.setAttribute('aria-controls', 'geography-map-modal');
          button.innerHTML = '<i class="fa-solid fa-pencil" aria-hidden="true"></i>';
          L.DomEvent.on(button, 'click', function (e) {
            L.DomEvent.stop(e);
            self.openModal();
          });
          L.DomEvent.disableClickPropagation(container);
          L.DomEvent.disableScrollPropagation(container);
          return container;
        }
      });

      this.drawControl = new DrawControl({ position: 'topleft' });
      this.drawControl.addTo(this.map);
    }

    openModal() {
      if (this.modalTrigger) {
        this.modalTrigger.click();
      }
      window.setTimeout(() => {
        this._ensureModalMap();
        this.disableDrawMode();
      }, 50);
    }

    _ensureModalMap(options = {}) {
      if (!this.modalMapContainer || typeof L === 'undefined') return;
      const { syncView = true } = options;
      const isGeographyModal = this.modalMapContainer.closest('.usa-modal--geography');
      if (isGeographyModal) {
        this.modalMapContainer.style.removeProperty('height');
        this.modalMapContainer.style.removeProperty('min-height');
      } else {
        const computedStyles = window.getComputedStyle(this.modalMapContainer);
        const computedHeight = computedStyles.height;
        const computedMinHeight = computedStyles.minHeight;
        const hasHeight =
          computedHeight &&
          computedHeight !== 'auto' &&
          computedHeight !== '0px';
        const hasMinHeight =
          computedMinHeight &&
          computedMinHeight !== 'auto' &&
          computedMinHeight !== '0px';
        if (!hasHeight) {
          this.modalMapContainer.style.height = '60vh';
        }
        if (!hasMinHeight) {
          this.modalMapContainer.style.minHeight = '26.25rem';
        }
      }
      if (!this.modalMap) {
        this.modalMap = L.map(this.modalMapContainer, {
          zoomControl: true,
          attributionControl: false
        });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19
        }).addTo(this.modalMap);
      }

      if (syncView) {
        this._syncModalMap();
      }
      this.modalMap.invalidateSize();
    }

    _syncModalMap() {
      if (!this.modalMap) return;
      if (this.pendingGeometry) {
        this.modalGeoLayer = this._renderGeometryOnMap(
          this.modalMap,
          this.modalGeoLayer,
          this.pendingGeometry
        );
      } else if (this.selectedGeometry) {
        this.modalGeoLayer = this._renderGeometryOnMap(
          this.modalMap,
          this.modalGeoLayer,
          this.selectedGeometry
        );
      } else {
        if (this.modalGeoLayer) {
          this.modalMap.removeLayer(this.modalGeoLayer);
          this.modalGeoLayer = null;
        }
        this._setDefaultView(this.modalMap, { usa: true });
      }
    }

    toggleDrawMode() {
      this._ensureModalMap({ syncView: false });
      if (!this.modalMap) return;
      if (this.isDrawing) {
        this.disableDrawMode();
      } else {
        this.enableDrawMode();
      }
    }

    enableDrawMode() {
      if (!this.modalMap) return;
      this.isDrawing = true;
      this.drawStartLatLng = null;
      if (this.drawButton) {
        this.drawButton.classList.add('geography-draw-button--active');
        this.drawButton.setAttribute('aria-pressed', 'true');
      }
      if (this.modalMap.dragging) this.modalMap.dragging.disable();
      if (this.modalMap.doubleClickZoom) this.modalMap.doubleClickZoom.disable();
      if (this.modalMap.scrollWheelZoom) this.modalMap.scrollWheelZoom.disable();
      this.modalMap.getContainer().style.cursor = 'crosshair';
      this.modalMap.on('mousedown', this.boundDrawStart);
      this.modalMap.on('mousemove', this.boundDrawMove);
      this.modalMap.on('mouseup', this.boundDrawEnd);
    }

    disableDrawMode() {
      if (!this.modalMap || !this.isDrawing) return;
      this.isDrawing = false;
      this.drawStartLatLng = null;
      this._clearDrawRect();
      if (this.drawButton) {
        this.drawButton.classList.remove('geography-draw-button--active');
        this.drawButton.setAttribute('aria-pressed', 'false');
      }
      if (this.modalMap.dragging) this.modalMap.dragging.enable();
      if (this.modalMap.doubleClickZoom) this.modalMap.doubleClickZoom.enable();
      if (this.modalMap.scrollWheelZoom) this.modalMap.scrollWheelZoom.enable();
      this.modalMap.getContainer().style.cursor = '';
      this.modalMap.off('mousedown', this.boundDrawStart);
      this.modalMap.off('mousemove', this.boundDrawMove);
      this.modalMap.off('mouseup', this.boundDrawEnd);
    }

    onDrawStart(e) {
      if (!this.isDrawing || !this.modalMap) return;
      this.drawStartLatLng = e.latlng;
      this._clearDrawRect();
      this.drawRect = L.rectangle(L.latLngBounds(e.latlng, e.latlng), {
        color: '#005ea2',
        weight: 2,
        fillOpacity: 0.05,
        interactive: false
      }).addTo(this.modalMap);
    }

    onDrawMove(e) {
      if (!this.isDrawing || !this.modalMap || !this.drawStartLatLng || !this.drawRect) return;
      const bounds = L.latLngBounds(this.drawStartLatLng, e.latlng);
      this.drawRect.setBounds(bounds);
    }

    onDrawEnd(e) {
      if (!this.isDrawing || !this.modalMap || !this.drawStartLatLng) return;
      const bounds = L.latLngBounds(this.drawStartLatLng, e.latlng);
      this.drawStartLatLng = null;
      if (!bounds.isValid() || bounds.getSouthWest().equals(bounds.getNorthEast())) {
        this._clearDrawRect();
        return;
      }
      this.setPendingBounds(bounds);
      this.disableDrawMode();
    }

    _clearDrawRect() {
      if (!this.modalMap || !this.drawRect) return;
      this.modalMap.removeLayer(this.drawRect);
      this.drawRect = null;
    }

    applyBoundsSelection(bounds) {
      const geometry = this.geometryFromBounds(bounds);
      this.selectedGeometry = geometry;
      this.pendingGeometry = null;
      this.updateApplyButtonState();
      this.showClearButton();
      this.displayGeometry(this.selectedGeometry);
      requestFilterFormSubmit(this.form);
    }

    setPendingBounds(bounds) {
      const geometry = this.geometryFromBounds(bounds);
      this.pendingGeometry = geometry;
      this.updateApplyButtonState();
      this._ensureModalMap();
      if (this.modalMap) {
        this.modalGeoLayer = this._renderGeometryOnMap(
          this.modalMap,
          this.modalGeoLayer,
          geometry
        );
      }
    }

    geometryFromBounds(bounds) {
      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();
      return {
        type: 'Polygon',
        coordinates: [[
          [sw.lng, sw.lat],
          [ne.lng, sw.lat],
          [ne.lng, ne.lat],
          [sw.lng, ne.lat],
          [sw.lng, sw.lat]
        ]]
      };
    }

    displayGeometry(geometry) {
        // Show this GeoJSON object on our map tile
      this._createMap();  // map object is in this.map
      if (!this.map) {
        console.error('Could not construct map');
        return;
      }
      this.geoLayer = this._renderGeometryOnMap(this.map, this.geoLayer, geometry);
      if (this.modalMap) {
        this._syncModalMap();
      }
    }

    displayNoGeometry() {
      this._createMap();
      if (!this.map) {
        console.error('Could not construct map');
        return;
      }
      this.pendingGeometry = null;
      this.updateApplyButtonState();
      if (this.geoLayer) {
        this.map.removeLayer(this.geoLayer);
        this.geoLayer = null;
      }
      this._setDefaultView(this.map);
      if (this.modalMap) {
        if (this.modalGeoLayer) {
          this.modalMap.removeLayer(this.modalGeoLayer);
          this.modalGeoLayer = null;
        }
        this._setDefaultView(this.modalMap, { usa: true });
      }
    }

    _renderGeometryOnMap(map, existingLayer, geometry) {
      if (!map) return existingLayer;
      if (existingLayer) {
        map.removeLayer(existingLayer);
      }
      const layer = L.geoJSON(geometry, {
        style: function () {
          return { color: '#005ea2', weight: 2, fillOpacity: 0.05 };
        },
        pointToLayer: function (_feature, latlng) {
          return L.marker(latlng);
        }
      }).addTo(map);

      const geoBounds = layer.getBounds();
      if (geoBounds.isValid()) {
        if (geoBounds.getSouthWest().equals(geoBounds.getNorthEast())) {
          map.setView(geoBounds.getSouthWest(), 8);
        } else {
          map.fitBounds(geoBounds.pad(0.1));
        }
      }
      return layer;
    }

    _setDefaultView(map, options = {}) {
      if (!map) return;
      const { usa = false } = options;
      if (usa) {
        map.setView([39.8283, -98.5795], 4);
        return;
      }
      map.setView([44.967243, -103.77155], 2);
    }

    updateApplyButtonState() {
      if (!this.modalApplyButton) return;
      const hasGeometry = !!(this.pendingGeometry || this.selectedGeometry);
      const hasPendingRelation = this.pendingSpatialWithin !== null;
      const hasPending =
        !!this.pendingGeometry || (hasPendingRelation && hasGeometry);
      this.modalApplyButton.disabled = !hasPending;
    }

    applyPendingGeometry() {
      const hasPendingGeometry = !!this.pendingGeometry;
      const hasPendingRelation = this.pendingSpatialWithin !== null;
      const hasGeometry = !!(this.pendingGeometry || this.selectedGeometry);
      if (!hasPendingGeometry && !hasPendingRelation) return;
      if (!hasGeometry) {
        this.pendingSpatialWithin = null;
        this.updateApplyButtonState();
        this.syncSpatialWithinRadios();
        return;
      }
      if (hasPendingGeometry) {
        this.selectedGeometry = this.pendingGeometry;
      }
      if (hasPendingRelation) {
        this.spatialWithin = this.pendingSpatialWithin;
      }
      this.pendingGeometry = null;
      this.pendingSpatialWithin = null;
      this.updateApplyButtonState();
      this.showClearButton();
      if (hasPendingGeometry) {
        this.displayGeometry(this.selectedGeometry);
      }
      this.markPostApplyScroll();
      requestFilterFormSubmit(this.form);
    }

    markPostApplyScroll() {
      try {
        sessionStorage.setItem('geography-apply-scroll', String(Date.now()));
      } catch (e) {
        // Ignore storage failures (private mode, disabled storage, etc.).
      }
    }

    handlePostApplyScroll() {
      let flag = null;
      try {
        flag = sessionStorage.getItem('geography-apply-scroll');
        sessionStorage.removeItem('geography-apply-scroll');
      } catch (e) {
        flag = null;
      }
      if (!flag) return;

      const target =
        document.getElementById('geography-input-label') ||
        document.getElementById('filter-geography');
      if (!target) return;

      window.requestAnimationFrame(() => {
        target.scrollIntoView({ block: 'start' });
        window.setTimeout(() => {
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }, 800);
      });
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
        requestFilterFormSubmit(this.form);
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
