/* global L */
(function (window) {
  const OSM_ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  function normalizeGeometry(value) {
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

  function parseSpatialWithinParam(value) {
    if (typeof value !== 'string') return true;
    const normalized = value.trim().toLowerCase();
    if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) return true;
    if (['false', '0', 'no', 'n', 'off'].includes(normalized)) return false;
    return true;
  }

  function loadSearchResultGeometries(scriptId) {
    const dataEl = document.getElementById(scriptId || 'geography-search-result-geometries');
    if (!dataEl) return [];
    try {
      const parsed = JSON.parse(dataEl.textContent || '[]');
      if (!Array.isArray(parsed)) return [];
      const geometries = [];
      parsed.forEach((entry) => {
        const geometry = normalizeGeometry(entry);
        if (geometry) {
          geometries.push(geometry);
        }
      });
      return geometries.slice(0, 20);
    } catch (_err) {
      return [];
    }
  }

  window.dataGovGeographyUtils = {
    OSM_ATTRIBUTION,
    normalizeGeometry,
    parseSpatialWithinParam,
    loadSearchResultGeometries,
  };
})(window);
