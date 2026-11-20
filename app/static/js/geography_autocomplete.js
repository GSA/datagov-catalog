/* global L */
const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

class GeographyAutocomplete extends BaseAutocomplete {
    constructor(options) {
        super(options, { apiEndpoint: '/api/location', minQueryLength: 2 });
        this.mapPanelNextStateStorageKey = 'datagov.geographyMapExpanded.nextState';
        this.selectedGeometry = null;
        this.selectedGeographyLabel = null;
        this.geoLayer = null;
        this.allGeographies = [];
        this.map = null;
        this.mapHandlersInitialized = false;
        this.drawControl = null;
        this.mapPanelTriggerButton = null;
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
        this.start();
    }

    init() {
        // Load any existing keywords from URL parameters
        this.loadExistingGeography();

        // Initialize suggested keywords click handlers
        this.initSuggestedGeography();

        this.bindInputEvents();

        // Sync selection to hidden inputs on form submit
        if (this.form) {
            this.form.addEventListener('submit', () => {
                this.syncHiddenInputs();
            });
        }

        if (this.mainSearchForm) {
            this.mainSearchForm.addEventListener('submit', () => {
                this.syncHiddenInputsToMainSearch();
                this.persistCurrentMapPanelStateForNextLoad();
            });
        }

        this.initMapPanel();
        this._initSidebarMapResize();
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
          if (this.mapPanelTriggerButton && this.mapPanelTriggerButton.isConnected) {
            this.mapPanelTriggerButton.focus();
          }
        });
      }

      const nextMapPanelState = this.consumeMapPanelStateOnNextLoad();
      if (nextMapPanelState !== null) {
        const shouldOpen = !!(nextMapPanelState && this.hasOpenEligibleMapPanelState());
        this.setMapPanelOpen(shouldOpen, { discardPending: false });
      }
    }

    isMapPanelOpen() {
      return !!(this.mapPanelElement && !this.mapPanelElement.hidden);
    }

    hasOpenEligibleMapPanelState() {
      return !!(this.selectedGeometry && this.spatialWithin);
    }

    setMapPanelStateOnNextLoad(isOpen) {
      if (typeof window === 'undefined' || !window.sessionStorage) return;
      try {
        window.sessionStorage.setItem(
          this.mapPanelNextStateStorageKey,
          isOpen ? '1' : '0'
        );
      } catch (_err) {
        // Ignore storage errors (privacy mode, quota, disabled storage).
      }
    }

    consumeMapPanelStateOnNextLoad() {
      if (typeof window === 'undefined' || !window.sessionStorage) return null;
      try {
        const nextState = window.sessionStorage.getItem(this.mapPanelNextStateStorageKey);
        window.sessionStorage.removeItem(this.mapPanelNextStateStorageKey);
        if (nextState === '1') return true;
        if (nextState === '0') return false;
        return null;
      } catch (_err) {
        return null;
      }
    }

    persistCurrentMapPanelStateForNextLoad() {
      const shouldOpen = !!(this.isMapPanelOpen() && this.hasOpenEligibleMapPanelState());
      this.setMapPanelStateOnNextLoad(shouldOpen);
    }

    setMapPanelOpen(isOpen, options = {}) {
      const { discardPending = true, scrollIntoView = false } = options;
      if (!this.mapPanelElement) return;

      if (isOpen) {
        this.mapPanelElement.hidden = false;
        this._ensureMapPanelMap();
        window.setTimeout(() => {
          if (this.mapPanelMap) {
            this.mapPanelMap.invalidateSize();
          }
          if (scrollIntoView) {
            this._scrollMapPanelIntoView();
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

    _scrollMapPanelIntoView() {
      if (!this.mapPanelElement || typeof window === 'undefined') return;
      const rect = this.mapPanelElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
      const isOutsideViewport = rect.top < 0 || rect.bottom > viewportHeight;
      if (!isOutsideViewport) return;
      this.mapPanelElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
        const existingLabel = urlParams.get('geography_label');
        this.spatialWithin = this.parseSpatialWithinParam(
          urlParams.get('spatial_within')
        );
        this.pendingSpatialWithin = null;
        if (existingGeometry) {
            // URL-encoded parameter is a string of a GeoJSON object
            this.selectedGeometry = JSON.parse(decodeURI(existingGeometry))
            this.selectedGeographyLabel = existingLabel || null;
            this.input.value = existingLabel || 'Area selected';
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

    // handle the click of the clear button
    clearClicked() {
      this.selectedGeometry = null;
      this.selectedGeographyLabel = null;
      this.input.value = '';
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

    _getGeographyFilterContent() {
      return document.getElementById('filter-geography');
    }

    _isGeographyFilterVisible() {
      const content = this._getGeographyFilterContent();
      return !!(content && !content.hidden);
    }

    _refreshSidebarMapLayout() {
      if (!this._isGeographyFilterVisible()) {
        return;
      }

      if (!this.map) {
        if (this.selectedGeometry) {
          this.displayGeometry(this.selectedGeometry);
        } else {
          this.displayNoGeometry();
        }
        return;
      }

      this.map.invalidateSize();
      if (this.geoLayer) {
        const bounds = this.geoLayer.getBounds();
        if (bounds && bounds.isValid()) {
          if (bounds.getSouthWest().equals(bounds.getNorthEast())) {
            this.map.setView(bounds.getSouthWest(), 8);
          } else {
            this.map.fitBounds(bounds.pad(0.1));
          }
        }
      } else {
        this._setDefaultView(this.map);
      }
    }

    _initSidebarMapResize() {
      const content = this._getGeographyFilterContent();
      if (!content || content.dataset.geographyMapResizeInit === 'true') {
        return;
      }
      content.dataset.geographyMapResizeInit = 'true';

      const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
          if (mutation.attributeName === 'hidden' && !content.hidden) {
            window.requestAnimationFrame(() => this._refreshSidebarMapLayout());
            break;
          }
        }
      });
      observer.observe(content, { attributes: true, attributeFilter: ['hidden'] });

      if (!content.hidden) {
        window.requestAnimationFrame(() => this._refreshSidebarMapLayout());
      }
    }

    _createMap() {
      // create a map and store it on this.map
      if (this.map) return;  // don't create the map if it already exists
      var el = document.getElementById('geography-map');
      if (!el) return;
      if (typeof L === 'undefined') return;
      var map = L.map(el, {
        zoomControl: true,
        attributionControl: true,
        scrollWheelZoom: false,
      });
      if (map.attributionControl && typeof map.attributionControl.setPrefix === 'function') {
        map.attributionControl.setPrefix(false);
      }
      var tiles = L.tileLayer('/maptiles/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: OSM_ATTRIBUTION
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
          self.mapPanelTriggerButton = button;
          L.DomEvent.on(button, 'click', function (e) {
            L.DomEvent.stop(e);
            self.openMapPanel();
          });
          button.addEventListener('keydown', function (e) {
            if (e.key === ' ' || e.key === 'Spacebar') {
              e.preventDefault();
            }
          });
          button.addEventListener('keyup', function (e) {
            if (e.key === ' ' || e.key === 'Spacebar') {
              e.preventDefault();
              button.click();
            }
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
      this.setMapPanelOpen(true, { discardPending: false, scrollIntoView: true });
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
          attributionControl: true
        });
        if (
          this.mapPanelMap.attributionControl &&
          typeof this.mapPanelMap.attributionControl.setPrefix === 'function'
        ) {
          this.mapPanelMap.attributionControl.setPrefix(false);
        }
        L.tileLayer('/maptiles/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: OSM_ATTRIBUTION
        }).addTo(this.mapPanelMap);
        this.mapPanelMap.on('zoomend', () => {
          this.mapPanelResultsLayer = this._renderSearchResultsLayer(
            this.mapPanelMap,
            this.mapPanelResultsLayer
          );
        });
      }
      this.mapPanelResultsLayer = this._renderSearchResultsLayer(
        this.mapPanelMap,
        this.mapPanelResultsLayer
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
        this.setMapPanelOpen(true, { discardPending: false, scrollIntoView: true });
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
      this.selectedGeographyLabel = 'Custom area';
      this.input.value = 'Custom area';
      this.pendingGeometry = null;
      this.updateApplyButtonState();
      this.showClearButton();
      this.displayGeometry(this.selectedGeometry);
      requestFilterFormSubmit(this.form);
    }

    setPendingBounds(bounds) {
      const geometry = this.geometryFromBounds(bounds);
      this.pendingGeometry = geometry;
      this.suppressResultLayerUntilReload = false;
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

    _rankClusterLabel(ranks) {
      const sorted = ranks.slice().sort((a, b) => a - b);
      const MAX_LISTED = 3;
      if (sorted.length <= MAX_LISTED) {
        return `#${sorted.join(', #')}`;
      }
      const shown = sorted.slice(0, MAX_LISTED - 1);
      const remaining = sorted.length - shown.length;
      return `#${shown.join(', #')} +${remaining} more`;
    }

    _estimateLabelSize(label) {
      const CHAR_WIDTH_PX = 8;
      const PADDING_PX = 16;
      const LABEL_HEIGHT_PX = 22;
      return { width: label.length * CHAR_WIDTH_PX + PADDING_PX, height: LABEL_HEIGHT_PX };
    }

    _labelRectsOverlap(a, b) {
      return (
        a.point.x < b.point.x + b.size.width &&
        a.point.x + a.size.width > b.point.x &&
        a.point.y < b.point.y + b.size.height &&
        a.point.y + a.size.height > b.point.y
      );
    }

    _buildRankClusterMarkers(map, rankEntries, rankIconForLabel) {
      if (typeof map.getZoom !== 'function' || map.getZoom() === undefined) {
        return rankEntries.map((entry) =>
          L.marker(entry.anchorLatLng, {
            icon: rankIconForLabel(this._rankClusterLabel([entry.rank])),
            interactive: false,
            keyboard: false,
            bubblingMouseEvents: false,
            zIndexOffset: 1000
          })
        );
      }
      let clusters = rankEntries.map((entry) => {
        const point = map.latLngToContainerPoint(entry.anchorLatLng);
        const label = this._rankClusterLabel([entry.rank]);
        return {
          anchorLatLng: entry.anchorLatLng,
          point,
          ranks: [entry.rank],
          label,
          size: this._estimateLabelSize(label)
        };
      });
      let merged = true;
      while (merged) {
        merged = false;
        for (let i = 0; i < clusters.length && !merged; i++) {
          for (let j = i + 1; j < clusters.length; j++) {
            if (!this._labelRectsOverlap(clusters[i], clusters[j])) continue;
            const combinedRanks = clusters[i].ranks.concat(clusters[j].ranks);
            const primary = clusters[i].ranks[0] <= clusters[j].ranks[0] ? clusters[i] : clusters[j];
            const label = this._rankClusterLabel(combinedRanks);
            const next = clusters.filter((_, index) => index !== i && index !== j);
            next.push({
              anchorLatLng: primary.anchorLatLng,
              point: primary.point,
              ranks: combinedRanks,
              label,
              size: this._estimateLabelSize(label)
            });
            clusters = next;
            merged = true;
            break;
          }
        }
      }
      return clusters.map((cluster) =>
        L.marker(cluster.anchorLatLng, {
          icon: rankIconForLabel(cluster.label),
          interactive: false,
          keyboard: false,
          bubblingMouseEvents: false,
          zIndexOffset: 1000
        })
      );
    }

    _renderSearchResultsLayer(map, existingLayer) {
      if (!map || typeof L === 'undefined') return existingLayer;
      if (existingLayer) {
        map.removeLayer(existingLayer);
      }
      if (this.pendingGeometry) {
        return null;
      }
      if (this.suppressResultLayerUntilReload) {
        return null;
      }
      if (!this.selectedGeometry) {
        return null;
      }
      if (!this._isWithinRelationActive()) {
        return null;
      }
      if (!this.searchResultGeometries || !this.searchResultGeometries.length) {
        return null;
      }
      const rankEntries = [];
      const rankAnchorForLayer = function (featureLayer) {
        if (featureLayer && typeof featureLayer.getBounds === 'function') {
          const bounds = featureLayer.getBounds();
          if (bounds && typeof bounds.isValid === 'function' && bounds.isValid()) {
            return bounds.getNorthWest();
          }
        }
        if (featureLayer && typeof featureLayer.getLatLng === 'function') {
          return featureLayer.getLatLng();
        }
        return null;
      };
      const rankIconForLabel = function (rankLabel) {
        return L.divIcon({
          className: 'geography-map-result-rank-marker',
          html: `<span class="geography-map-result-rank-label">${rankLabel}</span>`,
          iconSize: [1, 1],
          iconAnchor: [0, 0]
        });
      };
      const featureCollection = {
        type: 'FeatureCollection',
        features: this.searchResultGeometries.map((geometry, index) => ({
          type: 'Feature',
          properties: { rank: index + 1 },
          geometry: geometry
        }))
      };
      const geometryLayer = L.geoJSON(featureCollection, {
        interactive: false,
        style: function () {
          return { color: '#eb5f07', weight: 1.5, fillColor: '#f2938c', fillOpacity: 0.08 };
        },
        onEachFeature: function (feature, featureLayer) {
          const rank = feature && feature.properties ? feature.properties.rank : null;
          if (typeof rank !== 'number' || !featureLayer) {
            return;
          }
          const anchorLatLng = rankAnchorForLayer(featureLayer);
          if (!anchorLatLng) return;
          rankEntries.push({ rank, anchorLatLng });
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
      });
      const rankMarkers = this._buildRankClusterMarkers(map, rankEntries, rankIconForLabel);
      const layer = L.featureGroup([geometryLayer, ...rankMarkers]).addTo(map);
      if (typeof geometryLayer.bringToBack === 'function') {
        geometryLayer.bringToBack();
      }
      rankMarkers.forEach((marker) => {
        if (marker && typeof marker.bringToFront === 'function') {
          marker.bringToFront();
        }
      });
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
        this.suppressResultLayerUntilReload = true;
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

    async filterAndShowSuggestions(query) {
        // TODO: this calls the location search API every time, we could
        // try some caching to save on calls
        try {
            const params = new URLSearchParams({ q: query, size: 10 });
            const response = await fetch(`${this.apiEndpoint}s/search?${params}`);
            const data = await response.json();
            this.displaySuggestions(data.locations || []);
        } catch (error) {
            console.error('Error fetching geography suggestions:', error);
            this.hideSuggestions();
        }
    }

    getSuggestionLabel(item) {
        return item.display_name;
    }

    chooseSuggestion(item) {
        this.input.value = item.display_name;
        this.selectGeography(item);
        this.hideSuggestions();
    }

    async selectGeography(location_data) {
      // select this location, get the geometry and show it on the map
      var location_id = location_data.id;
      try {
        const response = await fetch(`${this.apiEndpoint}/${location_id}`);
        const data = await response.json();
        this.selectedGeometry = this.normalizeGeometry(data.geometry);
        if (!this.selectedGeometry) {
          throw new Error('Invalid location geometry');
        }
        this.selectedGeographyLabel = location_data.display_name || null;
        this.showClearButton();
        this.displayGeometry(this.selectedGeometry);
        this.setMapPanelOpen(true, { discardPending: false });
        requestFilterFormSubmit(this.form);
      } catch (error) {
        console.error('Error loading location data:', error);
      }
    }

    _syncSpatialHiddenInputs(form) {
        const hasGeometry = Boolean(this.selectedGeometry);
        // URI-encoding should be handled by form submission
        this.replaceHiddenInputs(form, 'spatial_geometry', hasGeometry ? [JSON.stringify(this.selectedGeometry)] : []);
        this.replaceHiddenInputs(form, 'spatial_within', hasGeometry ? [this.spatialWithin ? 'true' : 'false'] : []);
        this.replaceHiddenInputs(
            form,
            'geography_label',
            hasGeometry && this.selectedGeographyLabel ? [this.selectedGeographyLabel] : []
        );
    }

    // Sync geometry to hidden inputs in the filter form
    syncHiddenInputs() {
        this._syncSpatialHiddenInputs(this.form);
    }

    // Sync geometry to hidden inputs in the main search form
    syncHiddenInputsToMainSearch() {
        this._syncSpatialHiddenInputs(this.mainSearchForm);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const geographyAutocomplete = new GeographyAutocomplete({
        inputId: 'geography-input',
        suggestionsId: 'geography-suggestions',
        formId: 'filter-form',
        mainSearchFormId: 'main-search-form',
        apiEndpoint: '/api/location',
        debounceDelay: 300
    });
    window.dataGovGeographyAutocomplete = geographyAutocomplete;
});
