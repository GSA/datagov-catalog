/* global L */
(function () {
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
    var geometryAttr = el.getAttribute('data-geometry');

    var geometry = parseGeometry(geometryAttr);

    if (!geometry) return;

    var map = L.map(el, { zoomControl: true, attributionControl: false });
    var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19
    }).addTo(map);

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
    }
    return;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
