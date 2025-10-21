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
    if (minLon > maxLon) { var t1 = minLon; minLon = maxLon; maxLon = t1; }
    if (minLat > maxLat) { var t2 = minLat; minLat = maxLat; maxLat = t2; }
    return [[minLat, minLon], [maxLat, maxLon]]; // Leaflet LatLngBounds
  }

  function init() {
    var el = document.getElementById('dataset-map');
    if (!el) return;
    if (typeof L === 'undefined') return;
    var bbox = parseBBox(el.getAttribute('data-bbox'));
    if (!bbox) return;

    var map = L.map(el, { zoomControl: true, attributionControl: false });
    var tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19
    }).addTo(map);

    // Draw bbox or point
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


