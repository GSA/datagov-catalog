/* global L */
(function (window) {
  const OSM_ATTRIBUTION =
    (window.dataGovGeographyUtils && window.dataGovGeographyUtils.OSM_ATTRIBUTION) ||
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  function requestFilterFormSubmit(form, options = {}) {
    const submit = window.dataGovFilterSubmit;
    if (submit && typeof submit.request === 'function') {
      submit.request(form, options);
      return;
    }

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

  window.dataGovGeographyMapMixin = {
    initMapPanel() {
      this.mapPanelElement = document.getElementById('geography-map-expanded-panel');
      this.mapPanelCloseButton = document.getElementById('geography-map-expanded-close');
      this.mapPanelToggleButton = document.getElementById('geography-map-expanded-toggle');
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

      if (this.mapPanelToggleButton) {
        this.mapPanelToggleButton.addEventListener('click', () => {
          this.toggleMapPanel({ closeFacet: true });
        });
      }

      const nextMapPanelState = this.consumeMapPanelStateOnNextLoad();
      if (nextMapPanelState !== null) {
        const shouldOpen = !!(nextMapPanelState && this.hasOpenEligibleMapPanelState());
        this.setMapPanelOpen(shouldOpen, { discardPending: false });
      }
      this.updateMapPanelToggleState();
    }
,

    isMapPanelOpen() {
      return !!(this.mapPanelElement && !this.mapPanelElement.hidden);
    }
,

    hasOpenEligibleMapPanelState() {
      return !!(this.selectedGeometry && this.spatialWithin);
    }
,

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
,

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
,

    persistCurrentMapPanelStateForNextLoad() {
      const shouldOpen = !!(this.isMapPanelOpen() && this.hasOpenEligibleMapPanelState());
      this.setMapPanelStateOnNextLoad(shouldOpen);
    }
,

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
        this.updateMapPanelToggleState();
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
      this.updateMapPanelToggleState();
    }
,

    updateMapPanelToggleState() {
      if (!this.mapPanelToggleButton) return;
      const isOpen = this.isMapPanelOpen();
      this.mapPanelToggleButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      const label = this.mapPanelToggleButton.querySelector('.geography-map-toggle__label');
      const text = isOpen ? 'Hide large map' : 'Show large map';
      if (label) {
        label.textContent = text;
      }
      this.mapPanelToggleButton.setAttribute('aria-label', text);
    }
,

    toggleMapPanel(options = {}) {
      const { closeFacet = false } = options;
      if (this.isMapPanelOpen()) {
        this.setMapPanelOpen(false);
        return;
      }
      if (closeFacet) {
        this._closeGeographyFacetPanel();
      }
      this.setMapPanelOpen(true, { discardPending: false, scrollIntoView: true });
      this.disableDrawMode();
    }
,

    _closeGeographyFacetPanel() {
      const bar = window.dataGovFilterDropdowns;
      if (!bar || typeof bar.close !== 'function' || !bar.openFacet) {
        return;
      }
      if (bar.openFacet.key === 'geography') {
        bar.close({ skipDeferReset: true });
      }
    }
,

    openMapPanel() {
      this.toggleMapPanel({ closeFacet: true });
    }
,

    _scrollMapPanelIntoView() {
      if (!this.mapPanelElement || typeof window === 'undefined') return;
      const rect = this.mapPanelElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
      const isOutsideViewport = rect.top < 0 || rect.bottom > viewportHeight;
      if (!isOutsideViewport) return;
      this.mapPanelElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
,

    _createMap() {
      // create a map and store it on this.map
      if (this.map) return;  // don't create the map if it already exists
      var el = document.getElementById('geography-map');
      if (!el) return;
      if (typeof L === 'undefined') return;
      var map = L.map(el, { zoomControl: true, attributionControl: true });
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
,

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
,

    _addDrawControl() {
      if (!this.map || this.drawControl) return;
      const self = this;
      const DrawControl = L.Control.extend({
        onAdd: function () {
          const container = L.DomUtil.create('div', 'leaflet-bar geography-draw-control');
          const button = L.DomUtil.create('a', 'geography-draw-button', container);
          button.href = '#';
          button.title = 'Show or hide large map';
          button.setAttribute('role', 'button');
          button.setAttribute('aria-label', 'Show or hide large map');
          button.setAttribute('aria-controls', 'geography-map-expanded-panel');
          button.innerHTML = '<i class="fa-solid fa-pencil" aria-hidden="true"></i>';
          L.DomEvent.on(button, 'click', function (e) {
            L.DomEvent.stop(e);
            self.toggleMapPanel({ closeFacet: true });
          });
          L.DomEvent.disableClickPropagation(container);
          L.DomEvent.disableScrollPropagation(container);
          return container;
        }
      });

      this.drawControl = new DrawControl({ position: 'topleft' });
      this.drawControl.addTo(this.map);
    }
,

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
,

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
,

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
,

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
,

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
,

    _setDrawContainerDefaults() {
      this.drawContainer = this.mapPanelMap ? this.mapPanelMap.getContainer() : null;
      if (!this.drawContainer) return;
      this.prevTouchAction = this.drawContainer.style.touchAction;
      this.prevMsTouchAction = this.drawContainer.style.msTouchAction;
      this.drawContainer.style.touchAction = 'none';
      this.drawContainer.style.msTouchAction = 'none';
    }
,

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
,

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
,

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
,

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
,

    _preventDefaultEvent(e) {
      const originalEvent = e && (e.originalEvent || e);
      if (!originalEvent) return;
      if (typeof originalEvent.preventDefault === 'function' && originalEvent.cancelable !== false) {
        originalEvent.preventDefault();
      }
    }
,

    _getPointerId(e) {
      const originalEvent = e && (e.originalEvent || e);
      if (originalEvent && typeof originalEvent.pointerId === 'number') {
        return originalEvent.pointerId;
      }
      return null;
    }
,

    _isMultiTouch(e) {
      const originalEvent = e && (e.originalEvent || e);
      return !!(originalEvent && originalEvent.touches && originalEvent.touches.length > 1);
    }
,

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
,

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
,

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
,

    _clearDrawRect() {
      if (!this.mapPanelMap || !this.drawRect) return;
      this.mapPanelMap.removeLayer(this.drawRect);
      this.drawRect = null;
    }
,

    applyBoundsSelection(bounds) {
      const geometry = this.geometryFromBounds(bounds);
      this.selectedGeometry = geometry;
      this.spatialLabel = '';
      this.input.value = '';
      this.updateInputClearButtonVisibility();
      this.pendingGeometry = null;
      this.updateApplyButtonState();
      this.showClearButton();
      this.displayGeometry(this.selectedGeometry);
      // Geography is a deferred facet: stage the selection and let the facet's
      // Apply footer submit it.
    }
,

    setPendingBounds(bounds) {
      const geometry = this.geometryFromBounds(bounds);
      this.pendingGeometry = geometry;
      this.spatialLabel = '';
      this.input.value = '';
      this.updateInputClearButtonVisibility();
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
,

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
,

    displayGeometry(geometry) {
        // Show this GeoJSON object on our map tile
      this._createMap();  // map object is in this.map
      if (!this.map) {
        console.error('Could not construct map');
        return;
      }
      this.geoLayer = this._renderGeometryOnMap(this.map, this.geoLayer, geometry);
      this._scheduleInlineMapViewRefresh();
      if (this.mapPanelMap) {
        this._syncMapPanelMap();
      }
    }
,

    // Leaflet fitBounds is wrong when the map container was hidden or zero-sized
    // at init time (e.g. inside a closed filter panel). Re-measure and re-fit.
    refreshInlineMapView() {
      if (!this.map) return;
      this.map.invalidateSize();
      if (this.geoLayer) {
        this._fitMapToLayerBounds(this.map, this.geoLayer, { pad: 0.1, pointZoom: 8 });
      }
    }
,

    _scheduleInlineMapViewRefresh() {
      this.refreshInlineMapView();
      window.requestAnimationFrame(() => {
        this.refreshInlineMapView();
      });
    }
,

    // Called when the geography facet panel opens so the inline map is created
    // at full size and any staged geometry is visible/zoomed correctly.
    onFacetOpened() {
      if (this.selectedGeometry) {
        this.displayGeometry(this.selectedGeometry);
      } else {
        this.displayNoGeometry();
      }
      this._scheduleInlineMapViewRefresh();
    }
,

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
,

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
      const rankMarkers = [];
      const rankLabelForFeature = function (feature) {
        const rank = feature && feature.properties ? feature.properties.rank : null;
        if (typeof rank !== 'number') return null;
        return `#${rank}`;
      };
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
          const rankLabel = rankLabelForFeature(feature);
          if (!rankLabel || !featureLayer) {
            return;
          }
          const anchorLatLng = rankAnchorForLayer(featureLayer);
          if (!anchorLatLng) return;
          rankMarkers.push(
            L.marker(anchorLatLng, {
              icon: rankIconForLabel(rankLabel),
              interactive: false,
              keyboard: false,
              bubblingMouseEvents: false,
              zIndexOffset: 1000
            })
          );
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
,

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
,

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
,

    _setDefaultView(map, options = {}) {
      if (!map) return;
      const { usa = false } = options;
      if (usa) {
        map.setView([39.8283, -98.5795], 4);
        return;
      }
      map.setView([44.967243, -103.77155], 2);
    }
,

    updateApplyButtonState() {
      if (!this.mapPanelApplyButton) return;
      const hasGeometry = !!(this.pendingGeometry || this.selectedGeometry);
      const hasPendingRelation = this.pendingSpatialWithin !== null;
      const hasPending =
        !!this.pendingGeometry || (hasPendingRelation && hasGeometry);
      this.mapPanelApplyButton.disabled = !hasPending;
    }
,

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
      // The expanded draw panel has its own Apply, separate from the geography
      // facet's footer. Force past the deferred facet so this Apply submits.
      requestFilterFormSubmit(this.form, { force: true });
    }

  };
})(window);
