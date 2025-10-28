/* global L */
(function () {
  function parseBBox(bboxStr) {
    if (!bboxStr) return null;
    // Expecting "minLon,minLat,maxLon,maxLat" or a degenerate point bbox
    var parts = bboxStr.split(',').map(function (s) { return parseFloat(s.trim()); });
    if (parts.length !== 4 || parts.some(function (n) { return Number.isNaN(n); })) return null;
    var minLon = parts[0];
    var minLat = parts[1];
    var maxLon = parts[2];
    var maxLat = parts[3];
    // Normalize swapped inputs
    if (minLon > maxLon) { var tmpLon = minLon; minLon = maxLon; maxLon = tmpLon; }
    if (minLat > maxLat) { var tmpLat = minLat; minLat = maxLat; maxLat = tmpLat; }
    return [[minLat, minLon], [maxLat, maxLon]]; // Leaflet LatLngBounds
  }

  function parseGeometry(geometryStr) {
    if (!geometryStr) return null;
    try {
      var parsed = JSON.parse(geometryStr);
      if (!parsed || typeof parsed !== 'object') return null;
      return parsed;
    } catch (err) {
      return null;
    }
  }

  function init() {
    var el = document.getElementById('dataset-map');
    if (!el) return;
    if (typeof L === 'undefined') return;
    var bboxAttr = el.getAttribute('data-bbox');
    var geometryAttr = el.getAttribute('data-geometry');

    var geometry = parseGeometry(geometryAttr);
    var bbox = parseBBox(bboxAttr);

    if (!geometry && !bbox) return;

    var map = L.map(el, { zoomControl: true, attributionControl: false });
    var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19
    }).addTo(map);

    if (geometry) {
      var geoLayer = L.geoJSON(geometry, {
        style: function () {
          return { color: '#005ea2', weight: 2, fillOpacity: 0.05 };
        },
        pointToLayer: function (_feature, latlng) {
          return L.marker(latlng);
        }
      }).addTo(map);

      var geoBounds = geoLayer.getBounds();
      if (geoBounds.isValid()) {
        if (geoBounds.getSouthWest().equals(geoBounds.getNorthEast())) {
          map.setView(geoBounds.getSouthWest(), 8);
        } else {
          map.fitBounds(geoBounds.pad(0.1));
        }
      } else if (bbox) {
        drawBBox(map, bbox);
      }
      return;
    }

    if (bbox) {
      drawBBox(map, bbox);
    }
  }

  function drawBBox(map, bbox) {
    var southWest = bbox[0];
    var northEast = bbox[1];
    var bounds = L.latLngBounds(southWest, northEast);

    if (southWest[0] === northEast[0] && southWest[1] === northEast[1]) {
      L.marker(southWest).addTo(map);
      map.setView(southWest, 8);
    } else {
      L.rectangle(bounds, { color: '#005ea2', weight: 2, fillOpacity: 0.05 }).addTo(map);
      map.fitBounds(bounds.pad(0.1));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
