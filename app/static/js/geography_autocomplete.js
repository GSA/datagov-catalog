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
        this.mapPanelReopenStorageKey = 'datagov.geographyMapExpanded.reopenOnce';
        this.mapPanelLegacyStateStorageKey = 'datagov.geographyMapExpanded.open';
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
        this.mapPanelCloseButton = null;
        this.mapPanelElement = null;
        this.mapPanelMapContainer = null;
        this.mapPanelMap = null;
        this.mapPanelGeoLayer = null;
        this.searchResultGeometries = this.loadSearchResultGeometries();
        this.mapPanelResultsLayer = null;
        this.mapPanelApplyButton = null;
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

        this.initMapPanel();
    }

    loadSearchResultGeometries() {
      const dataEl = document.getElementById('geography-search-result-geometries');
      if (!dataEl) return [];
      try {
        const parsed = JSON.parse(dataEl.textContent || '[]');
        if (!Array.isArray(parsed)) return [];
        const geometries = [];
        parsed.forEach((entry) => {
          const geometry = this.normalizeGeometry(entry);
          if (geometry) {
            geometries.push(geometry);
          }
        });
        return geometries.slice(0, 20);
      } catch (_err) {
        return [];
      }
    }

    normalizeGeometry(value) {
      if (!value) return null;
      let geometry = value;
      if (typeof geometry === 'string') {
        try {
          geometry = JSON.parse(geometry);
        } catch (_err) {
          return null;
        }
      }
      if (!geometry || typeof geometry !== 'object') return null;
      if (typeof geometry.type !== 'string') return null;
      return geometry;
    }

    initMapPanel() {
      this.mapPanelElement = document.getElementById('geography-map-expanded-panel');
      this.mapPanelCloseButton = document.getElementById('geography-map-expanded-close');
      this.mapPanelMapContainer = document.getElementById('geography-map-expanded-map');
      this.drawButton = document.getElementById('geography-modal-draw-toggle');
      this.mapPanelApplyButton = document.getElementById('geography-modal-apply');
      this.spatialWithinRadios = this.mapPanelElement
        ? this.mapPanelElement.querySelectorAll('input[name="spatial_within"]')
        : null;

      if (this.drawButton) {
        this.drawButton.setAttribute('aria-pressed', 'false');
        this.drawButton.addEventListener('click', () => {
          this.toggleDrawMode();
        });
      }

      if (this.mapPanelApplyButton) {
        this.mapPanelApplyButton.addEventListener('click', () => {
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

      if (this.mapPanelCloseButton) {
        this.mapPanelCloseButton.addEventListener('click', () => {
          this.setMapPanelOpen(false);
        });
      }

      this.clearLegacyMapPanelState();
      if (this.consumeMapPanelReopenState()) {
        this.setMapPanelOpen(true, { discardPending: false });
      }
    }

    isMapPanelOpen() {
      return !!(this.mapPanelElement && !this.mapPanelElement.hidden);
    }

    setMapPanelReopenOnNextLoad() {
      if (typeof window === 'undefined' || !window.sessionStorage) return;
      try {
        window.sessionStorage.setItem(this.mapPanelReopenStorageKey, '1');
      } catch (_err) {
        // Ignore storage errors (privacy mode, quota, disabled storage).
      }
    }

    clearMapPanelReopenState() {
      if (typeof window === 'undefined' || !window.sessionStorage) return;
      try {
        window.sessionStorage.removeItem(this.mapPanelReopenStorageKey);
      } catch (_err) {
        // Ignore storage errors (privacy mode, quota, disabled storage).
      }
    }

    consumeMapPanelReopenState() {
      if (typeof window === 'undefined' || !window.sessionStorage) return false;
      try {
        const shouldReopen =
          window.sessionStorage.getItem(this.mapPanelReopenStorageKey) === '1';
        window.sessionStorage.removeItem(this.mapPanelReopenStorageKey);
        return shouldReopen;
      } catch (_err) {
        return false;
      }
    }

    clearLegacyMapPanelState() {
      if (typeof window === 'undefined' || !window.sessionStorage) return;
      try {
        window.sessionStorage.removeItem(this.mapPanelLegacyStateStorageKey);
      } catch (_err) {
        // Ignore storage errors (privacy mode, quota, disabled storage).
      }
    }

    setMapPanelOpen(isOpen, options = {}) {
      const { discardPending = true } = options;
      if (!this.mapPanelElement) return;

      if (isOpen) {
        this.mapPanelElement.hidden = false;
        this._ensureMapPanelMap();
        window.setTimeout(() => {
          if (this.mapPanelMap) {
            this.mapPanelMap.invalidateSize();
          }
        }, 0);
        return;
      }

      this.disableDrawMode();
      this.mapPanelElement.hidden = true;

      if (discardPending) {
        this.pendingGeometry = null;
        this.pendingSpatialWithin = null;
        this.syncSpatialWithinRadios();
        this.updateApplyButtonState();
        this._syncMapPanelMap();
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
      var tiles = L.tileLayer('/maptiles/{z}/{x}/{y}.png', {
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
          button.title = 'Open map tools to draw a box';
          button.setAttribute('role', 'button');
          button.setAttribute('aria-label', 'Open map tools to draw a box');
          button.setAttribute('aria-controls', 'geography-map-expanded-panel');
          button.innerHTML = '<i class="fa-solid fa-pencil" aria-hidden="true"></i>';
          L.DomEvent.on(button, 'click', function (e) {
            L.DomEvent.stop(e);
            self.openMapPanel();
          });
          L.DomEvent.disableClickPropagation(container);
          L.DomEvent.disableScrollPropagation(container);
          return container;
        }
      });

      this.drawControl = new DrawControl({ position: 'topleft' });
      this.drawControl.addTo(this.map);
    }

    openMapPanel() {
      this.setMapPanelOpen(true, { discardPending: false });
      this.disableDrawMode();
    }

    _ensureMapPanelMap(options = {}) {
      if (!this.mapPanelMapContainer || typeof L === 'undefined') return;
      const { syncView = true } = options;
      const computedStyles = window.getComputedStyle(this.mapPanelMapContainer);
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
        this.mapPanelMapContainer.style.height = '24rem';
      }
      if (!hasMinHeight) {
        this.mapPanelMapContainer.style.minHeight = '18rem';
      }
      if (!this.mapPanelMap) {
        this.mapPanelMap = L.map(this.mapPanelMapContainer, {
          zoomControl: true,
          attributionControl: false
        });
        L.tileLayer('/maptiles/{z}/{x}/{y}.png', {
          maxZoom: 19
        }).addTo(this.mapPanelMap);
      }
      this.modalResultsLayer = this._renderSearchResultsLayer(
        this.modalMap,
        this.modalResultsLayer
      );

      if (syncView) {
        this._syncMapPanelMap();
      }
      this.mapPanelMap.invalidateSize();
    }

    _syncMapPanelMap() {
      if (!this.mapPanelMap) return;
      this.mapPanelResultsLayer = this._renderSearchResultsLayer(
        this.mapPanelMap,
        this.mapPanelResultsLayer
      );
      if (this.pendingGeometry) {
        this.mapPanelGeoLayer = this._renderGeometryOnMap(
          this.mapPanelMap,
          this.mapPanelGeoLayer,
          this.pendingGeometry
        );
      } else if (this.selectedGeometry) {
        this.mapPanelGeoLayer = this._renderGeometryOnMap(
          this.mapPanelMap,
          this.mapPanelGeoLayer,
          this.selectedGeometry
        );
      } else {
        if (this.mapPanelGeoLayer) {
          this.mapPanelMap.removeLayer(this.mapPanelGeoLayer);
          this.mapPanelGeoLayer = null;
        }
        const fittedToResults = this._fitMapToLayerBounds(this.mapPanelMap, this.mapPanelResultsLayer, {
          pad: 0.08,
          pointZoom: 6
        });
        if (!fittedToResults) {
          this._setDefaultView(this.mapPanelMap, { usa: true });
        }
      }
    }

    toggleDrawMode() {
      if (!this.isMapPanelOpen()) {
        this.setMapPanelOpen(true, { discardPending: false });
      }
      this._ensureMapPanelMap({ syncView: false });
      if (!this.mapPanelMap) return;
      if (this.isDrawing) {
        this.disableDrawMode();
      } else {
        this.enableDrawMode();
      }
    }

    enableDrawMode() {
      if (!this.mapPanelMap) return;
      this.isDrawing = true;
      this.drawStartLatLng = null;
      this._setDrawContainerDefaults();
      if (this.drawButton) {
        this.drawButton.classList.add('geography-draw-button--active');
        this.drawButton.setAttribute('aria-pressed', 'true');
      }
      if (this.mapPanelMap.dragging) this.mapPanelMap.dragging.disable();
      if (this.mapPanelMap.doubleClickZoom) this.mapPanelMap.doubleClickZoom.disable();
      if (this.mapPanelMap.scrollWheelZoom) this.mapPanelMap.scrollWheelZoom.disable();
      if (this.mapPanelMap.touchZoom) this.mapPanelMap.touchZoom.disable();
      if (this.mapPanelMap.tap) this.mapPanelMap.tap.disable();
      if (this.drawContainer) {
        this.drawContainer.style.cursor = 'crosshair';
      }
      this._bindDrawEvents();
    }

    disableDrawMode() {
      if (!this.mapPanelMap || !this.isDrawing) return;
      this.isDrawing = false;
      this.drawStartLatLng = null;
      this.activePointerId = null;
      this._clearDrawRect();
      if (this.drawButton) {
        this.drawButton.classList.remove('geography-draw-button--active');
        this.drawButton.setAttribute('aria-pressed', 'false');
      }
      if (this.mapPanelMap.dragging) this.mapPanelMap.dragging.enable();
      if (this.mapPanelMap.doubleClickZoom) this.mapPanelMap.doubleClickZoom.enable();
      if (this.mapPanelMap.scrollWheelZoom) this.mapPanelMap.scrollWheelZoom.enable();
      if (this.mapPanelMap.touchZoom) this.mapPanelMap.touchZoom.enable();
      if (this.mapPanelMap.tap) this.mapPanelMap.tap.enable();
      if (this.drawContainer) {
        this.drawContainer.style.cursor = '';
        this._restoreDrawContainerDefaults();
      }
      this._unbindDrawEvents();
    }

    _setDrawContainerDefaults() {
      this.drawContainer = this.mapPanelMap ? this.mapPanelMap.getContainer() : null;
      if (!this.drawContainer) return;
      this.prevTouchAction = this.drawContainer.style.touchAction;
      this.prevMsTouchAction = this.drawContainer.style.msTouchAction;
      this.drawContainer.style.touchAction = 'none';
      this.drawContainer.style.msTouchAction = 'none';
    }

    _restoreDrawContainerDefaults() {
      if (!this.drawContainer) return;
      if (this.prevTouchAction !== null) {
        this.drawContainer.style.touchAction = this.prevTouchAction;
      } else {
        this.drawContainer.style.removeProperty('touch-action');
      }
      if (this.prevMsTouchAction !== null) {
        this.drawContainer.style.msTouchAction = this.prevMsTouchAction;
      } else {
        this.drawContainer.style.removeProperty('ms-touch-action');
      }
      this.prevTouchAction = null;
      this.prevMsTouchAction = null;
    }

    _bindDrawEvents() {
      if (!this.mapPanelMap) return;
      if (this.usePointerEvents) {
        if (!this.drawContainer) return;
        L.DomEvent.on(this.drawContainer, 'pointerdown', this.boundDrawStart, this);
        L.DomEvent.on(this.drawContainer, 'pointermove', this.boundDrawMove, this);
        L.DomEvent.on(this.drawContainer, 'pointerup', this.boundDrawEnd, this);
        L.DomEvent.on(this.drawContainer, 'pointercancel', this.boundDrawEnd, this);
        return;
      }

      this.mapPanelMap.on('mousedown', this.boundDrawStart);
      this.mapPanelMap.on('mousemove', this.boundDrawMove);
      this.mapPanelMap.on('mouseup', this.boundDrawEnd);
      this.mapPanelMap.on('touchstart', this.boundDrawStart);
      this.mapPanelMap.on('touchmove', this.boundDrawMove);
      this.mapPanelMap.on('touchend', this.boundDrawEnd);
      this.mapPanelMap.on('touchcancel', this.boundDrawEnd);
    }

    _unbindDrawEvents() {
      if (!this.mapPanelMap) return;
      if (this.usePointerEvents) {
        if (!this.drawContainer) return;
        L.DomEvent.off(this.drawContainer, 'pointerdown', this.boundDrawStart, this);
        L.DomEvent.off(this.drawContainer, 'pointermove', this.boundDrawMove, this);
        L.DomEvent.off(this.drawContainer, 'pointerup', this.boundDrawEnd, this);
        L.DomEvent.off(this.drawContainer, 'pointercancel', this.boundDrawEnd, this);
        return;
      }

      this.mapPanelMap.off('mousedown', this.boundDrawStart);
      this.mapPanelMap.off('mousemove', this.boundDrawMove);
      this.mapPanelMap.off('mouseup', this.boundDrawEnd);
      this.mapPanelMap.off('touchstart', this.boundDrawStart);
      this.mapPanelMap.off('touchmove', this.boundDrawMove);
      this.mapPanelMap.off('touchend', this.boundDrawEnd);
      this.mapPanelMap.off('touchcancel', this.boundDrawEnd);
    }

    _getEventLatLng(e) {
      if (e && e.latlng) return e.latlng;
      if (!this.mapPanelMap || !e) return null;
      const originalEvent = e.originalEvent || e;
      let sourceEvent = originalEvent;
      if (originalEvent.touches && originalEvent.touches.length) {
        sourceEvent = originalEvent.touches[0];
      } else if (originalEvent.changedTouches && originalEvent.changedTouches.length) {
        sourceEvent = originalEvent.changedTouches[0];
      }
      if (!sourceEvent || typeof sourceEvent.clientX !== 'number') return null;
      const point = this.mapPanelMap.mouseEventToContainerPoint(sourceEvent);
      return this.mapPanelMap.containerPointToLatLng(point);
    }

    _preventDefaultEvent(e) {
      const originalEvent = e && (e.originalEvent || e);
      if (!originalEvent) return;
      if (typeof originalEvent.preventDefault === 'function' && originalEvent.cancelable !== false) {
        originalEvent.preventDefault();
      }
    }

    _getPointerId(e) {
      const originalEvent = e && (e.originalEvent || e);
      if (originalEvent && typeof originalEvent.pointerId === 'number') {
        return originalEvent.pointerId;
      }
      return null;
    }

    _isMultiTouch(e) {
      const originalEvent = e && (e.originalEvent || e);
      return !!(originalEvent && originalEvent.touches && originalEvent.touches.length > 1);
    }

    onDrawStart(e) {
      if (!this.isDrawing || !this.mapPanelMap) return;
      if (this._isMultiTouch(e)) return;
      this._preventDefaultEvent(e);
      const pointerId = this._getPointerId(e);
      if (pointerId !== null) {
        this.activePointerId = pointerId;
        const originalEvent = e && (e.originalEvent || e);
        const target = originalEvent && originalEvent.target;
        if (target && typeof target.setPointerCapture === 'function') {
          target.setPointerCapture(pointerId);
        }
      }
      const latlng = this._getEventLatLng(e);
      if (!latlng) return;
      this.drawStartLatLng = latlng;
      this._clearDrawRect();
      this.drawRect = L.rectangle(L.latLngBounds(latlng, latlng), {
        color: '#005ea2',
        weight: 2,
        fillOpacity: 0.05,
        interactive: false
      }).addTo(this.mapPanelMap);
    }

    onDrawMove(e) {
      if (!this.isDrawing || !this.mapPanelMap || !this.drawStartLatLng || !this.drawRect) return;
      if (this._isMultiTouch(e)) return;
      this._preventDefaultEvent(e);
      const pointerId = this._getPointerId(e);
      if (this.activePointerId !== null) {
        if (pointerId === null || pointerId !== this.activePointerId) return;
      }
      const latlng = this._getEventLatLng(e);
      if (!latlng) return;
      const bounds = L.latLngBounds(this.drawStartLatLng, latlng);
      this.drawRect.setBounds(bounds);
    }

    onDrawEnd(e) {
      if (!this.isDrawing || !this.mapPanelMap || !this.drawStartLatLng) return;
      this._preventDefaultEvent(e);
      const pointerId = this._getPointerId(e);
      if (this.activePointerId !== null) {
        if (pointerId === null || pointerId !== this.activePointerId) return;
      }
      if (pointerId !== null) {
        const originalEvent = e && (e.originalEvent || e);
        const target = originalEvent && originalEvent.target;
        if (target && typeof target.releasePointerCapture === 'function') {
          try {
            target.releasePointerCapture(pointerId);
          } catch (err) {
            // Ignore capture release failures (e.g., if not captured).
          }
        }
      }
      const latlng = this._getEventLatLng(e);
      if (!latlng) return;
      const bounds = L.latLngBounds(this.drawStartLatLng, latlng);
      this.drawStartLatLng = null;
      this.activePointerId = null;
      if (!bounds.isValid() || bounds.getSouthWest().equals(bounds.getNorthEast())) {
        this._clearDrawRect();
        return;
      }
      this.setPendingBounds(bounds);
      this.disableDrawMode();
    }

    _clearDrawRect() {
      if (!this.mapPanelMap || !this.drawRect) return;
      this.mapPanelMap.removeLayer(this.drawRect);
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
      this._ensureMapPanelMap();
      if (this.mapPanelMap) {
        this.mapPanelGeoLayer = this._renderGeometryOnMap(
          this.mapPanelMap,
          this.mapPanelGeoLayer,
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
      if (this.mapPanelMap) {
        this._syncMapPanelMap();
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
      if (this.mapPanelMap) {
        if (this.mapPanelGeoLayer) {
          this.mapPanelMap.removeLayer(this.mapPanelGeoLayer);
          this.mapPanelGeoLayer = null;
        }
        this.mapPanelResultsLayer = this._renderSearchResultsLayer(
          this.mapPanelMap,
          this.mapPanelResultsLayer
        );
        const mapPanelFittedToResults = this._fitMapToLayerBounds(
          this.mapPanelMap,
          this.mapPanelResultsLayer,
          { pad: 0.08, pointZoom: 6 }
        );
        if (!mapPanelFittedToResults) {
          this._setDefaultView(this.mapPanelMap, { usa: true });
        }
      }
    }

    _renderSearchResultsLayer(map, existingLayer) {
      if (!map || typeof L === 'undefined') return existingLayer;
      if (existingLayer) {
        map.removeLayer(existingLayer);
      }
      if (!this.searchResultGeometries || !this.searchResultGeometries.length) {
        return null;
      }
      const featureCollection = {
        type: 'FeatureCollection',
        features: this.searchResultGeometries.map((geometry, index) => ({
          type: 'Feature',
          properties: { rank: index + 1 },
          geometry: geometry
        }))
      };
      const layer = L.geoJSON(featureCollection, {
        interactive: false,
        style: function () {
          return { color: '#eb5f07', weight: 1.5, fillColor: '#f2938c', fillOpacity: 0.08 };
        },
        pointToLayer: function (_feature, latlng) {
          return L.circleMarker(latlng, {
            radius: 4,
            color: '#eb5f07',
            weight: 1,
            fillColor: '#ffbe2e',
            fillOpacity: 0.85,
            interactive: false
          });
        }
      }).addTo(map);
      if (typeof layer.bringToBack === 'function') {
        layer.bringToBack();
      }
      return layer;
    }

    _fitMapToLayerBounds(map, layer, options = {}) {
      if (!map || !layer || typeof layer.getBounds !== 'function') return false;
      const bounds = layer.getBounds();
      if (!bounds || !bounds.isValid()) return false;
      const { pad = 0.1, pointZoom = 6 } = options;
      if (bounds.getSouthWest().equals(bounds.getNorthEast())) {
        map.setView(bounds.getSouthWest(), pointZoom);
      } else {
        map.fitBounds(bounds.pad(pad));
      }
      return true;
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
      if (!this.mapPanelApplyButton) return;
      const hasGeometry = !!(this.pendingGeometry || this.selectedGeometry);
      const hasPendingRelation = this.pendingSpatialWithin !== null;
      const hasPending =
        !!this.pendingGeometry || (hasPendingRelation && hasGeometry);
      this.mapPanelApplyButton.disabled = !hasPending;
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
      if (this.spatialWithin) {
        this.setMapPanelReopenOnNextLoad();
      } else {
        this.clearMapPanelReopenState();
      }
      requestFilterFormSubmit(this.form);
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
