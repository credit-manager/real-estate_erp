/* ============================================================
   Project Master Plan Map — Interactive SVG Visualization
   ============================================================ */

let mapProjectId = null;
let mapUnits = [];
let mapBuildings = [];
let selectedUnit = null;

// Status color mapping
const STATUS_COLORS = {
  available: '#22c55e',
  reserved: '#f59e0b',
  sold: '#ef4444',
  rented: '#3b82f6',
  maintenance: '#8b5cf6'
};

const STATUS_LABELS = {
  available: t('status.available'),
  reserved: t('status.reserved'),
  sold: t('status.sold'),
  rented: t('status.rented'),
  maintenance: t('status.maintenance')
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', async () => {
  await loadProjectsForMap();
  document.getElementById('map-project-select').addEventListener('change', (e) => {
    mapProjectId = e.target.value || null;
    if (mapProjectId) loadProjectMap();
  });
});

async function loadProjectsForMap() {
  try {
    const projects = await api.get('/api/projects');
    const list = Array.isArray(projects) ? projects : (projects.items || []);
    const sel = document.getElementById('map-project-select');
    sel.innerHTML = `<option value="">${t('common.selectProject')}</option>` +
      list.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
  } catch (e) { toastError(e); }
}

async function loadProjectMap() {
  if (!mapProjectId) return;
  const loading = document.getElementById('map-loading');
  const container = document.getElementById('map-svg-container');
  loading.style.display = 'flex';
  container.innerHTML = '';

  try {
    const [unitsRes, buildingsRes] = await Promise.all([
      api.get(`/api/units?project_id=${mapProjectId}`),
      api.get(`/api/realestate/buildings?project_id=${mapProjectId}`)
    ]);
    mapUnits = Array.isArray(unitsRes) ? unitsRes : (unitsRes.items || []);
    mapBuildings = Array.isArray(buildingsRes) ? buildingsRes : (buildingsRes.items || []);

    // Update KPIs
    updateMapKPIs();

    // Generate and render SVG map
    const svg = generateMapSVG();
    container.innerHTML = svg;
    loading.style.display = 'none';

    // Attach click events to unit elements
    attachUnitEvents();

  } catch (e) {
    loading.style.display = 'none';
    toastError(e);
  }
}

function updateMapKPIs() {
  const stats = {
    total: mapUnits.length,
    available: mapUnits.filter(u => u.status === 'available').length,
    reserved: mapUnits.filter(u => u.status === 'reserved').length,
    sold: mapUnits.filter(u => u.status === 'sold').length,
    rented: mapUnits.filter(u => u.status === 'rented').length
  };
  setText('kpi-total', stats.total);
  setText('kpi-available', stats.available);
  setText('kpi-reserved', stats.reserved);
  setText('kpi-sold', stats.sold);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

/**
 * Generate SVG map from building/unit data.
 * This creates a simplified grid layout - in production you'd use actual coordinates.
 */
function generateMapSVG() {
  if (!mapUnits.length) {
    return `<div class="empty-state" style="height:100%;display:flex;align-items:center;justify-content:center;color:var(--muted-foreground);">
      ${t('projects.noUnitsForMap')}
    </div>`;
  }

  // Group units by building
  const unitsByBuilding = {};
  mapUnits.forEach(u => {
    const bldgId = u.building_id || 0;
    if (!unitsByBuilding[bldgId]) unitsByBuilding[bldgId] = [];
    unitsByBuilding[bldgId].push(u);
  });

  // Building dimensions (simplified grid)
  const buildingWidth = 300;
  const buildingHeight = 200;
  const buildingGap = 40;
  const unitSize = { w: 60, h: 40 };
  const unitGap = 8;
  const labelHeight = 20;

  let svgParts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;font-family:inherit;">'];

  // Styles
  svgParts.push(`
    <defs>
      <style>
        .unit-rect { cursor: pointer; transition: filter 0.2s, stroke 0.2s; }
        .unit-rect:hover { filter: brightness(1.1); stroke: #fff; stroke-width: 2; }
        .unit-rect.selected { stroke: #fff; stroke-width: 3; filter: drop-shadow(0 0 4px rgba(0,0,0,0.5)); }
        .unit-label { font-size: 10px; fill: #1e293b; text-anchor: middle; pointer-events: none; }
        .building-title { font-size: 14px; font-weight: 600; fill: #0f172a; text-anchor: middle; }
        .floor-label { font-size: 11px; fill: #64748b; text-anchor: middle; }
        .legend-box { fill: none; }
      </style>
    </defs>
  `);

  let xOffset = 50;
  let maxY = 50;

  Object.entries(unitsByBuilding).forEach(([bldgId, units]) => {
    const building = mapBuildings.find(b => b.id == bldgId) || { name: t('common.building') + ' ' + bldgId };
    const floors = [...new Set(units.map(u => u.floor || '1').sort())];

    // Building title
    svgParts.push(`<text x="${xOffset + buildingWidth/2}" y="30" class="building-title">${escapeHtml(building.name)}</text>`);

    // Group units by floor
    floors.forEach((floor, floorIdx) => {
      const floorUnits = units.filter(u => (u.floor || '1') == floor);
      const cols = Math.min(floorUnits.length, 4);
      const startX = xOffset + (buildingWidth - (cols * unitSize.w + (cols-1)*unitGap)) / 2;
      const floorY = 50 + floorIdx * (unitSize.h + labelHeight + unitGap + 30);

      // Floor label
      svgParts.push(`<text x="${xOffset + buildingWidth/2}" y="${floorY - 5}" class="floor-label">${t('common.floor')} ${escapeHtml(floor)}</text>`);

      floorUnits.forEach((unit, idx) => {
        const ux = startX + idx * (unitSize.w + unitGap);
        const uy = floorY + 15;
        const color = STATUS_COLORS[unit.status] || '#94a3b8';
        const unitId = `unit-${unit.id}`;

        // Unit rectangle
        svgParts.push(`
          <rect id="${unitId}" class="unit-rect" x="${ux}" y="${uy}"
                width="${unitSize.w}" height="${unitSize.h}"
                rx="4" fill="${color}"
                data-unit-id="${unit.id}" data-unit-code="${escapeHtml(unit.unit_code)}"
                data-status="${unit.status}" />
        `);

        // Unit code label
        svgParts.push(`
          <text class="unit-label" x="${ux + unitSize.w/2}" y="${uy + unitSize.h + 12}">
            ${escapeHtml(unit.unit_code)}
          </text>
        `);
      });

      maxY = Math.max(maxY, floorY + unitSize.h + labelHeight + 30);
    });

    xOffset += buildingWidth + buildingGap;
  });

  // Update viewBox to fit content
  const totalWidth = xOffset + 50;
  const totalHeight = maxY + 50;

  // Replace the viewBox in the opening SVG tag
  svgParts[0] = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${totalWidth} ${totalHeight}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;font-family:inherit;">`;

  svgParts.push('</svg>');
  return svgParts.join('');
}

function attachUnitEvents() {
  document.querySelectorAll('.unit-rect').forEach(rect => {
    rect.addEventListener('click', (e) => {
      const unitId = parseInt(e.target.dataset.unitId);
      showUnitDetail(unitId);
    });
  });
}

function showUnitDetail(unitId) {
  const unit = mapUnits.find(u => u.id === unitId);
  if (!unit) return;
  selectedUnit = unit;

  // Remove previous selection
  document.querySelectorAll('.unit-rect.selected').forEach(el => el.classList.remove('selected'));
  const rect = document.getElementById(`unit-${unitId}`);
  if (rect) rect.classList.add('selected');

  // Populate modal
  setText('map-unit-code', unit.unit_code);
  setText('map-unit-status', STATUS_LABELS[unit.status] || unit.status);
  setText('map-unit-area', unit.area ? `${unit.area} ${t('realestate.sqm')}` : '—');
  setText('map-unit-price', unit.price ? formatMoney(unit.price) : '—');
  setText('map-unit-customer', unit.customer_name || unit.owner_name || '—');
  setText('map-unit-building', unit.building_name || '—');
  setText('map-unit-floor', unit.floor || unit.floor_label || '—');
  setText('map-unit-type', unit.unit_type_name || unit.unit_type || '—');

  document.getElementById('map-unit-modal-title').textContent = `${t('projects.unitDetails')} — ${unit.unit_code}`;
  document.getElementById('map-unit-modal').classList.add('active');
}

function openUnitFromMap() {
  if (!selectedUnit) return;
  closeModal('map-unit-modal');
  // Navigate to real-estate page with unit selected
  window.location.href = `/real-estate#re-units`;
  // Could also open unit modal directly if on same page
}

function loadProjectMap() {
  // Already implemented above
  const loading = document.getElementById('map-loading');
  const container = document.getElementById('map-svg-container');
  loading.style.display = 'flex';
  container.innerHTML = '';

  // This will be called after project select change
  if (!mapProjectId) return;

  api.get(`/api/units?project_id=${mapProjectId}`).then(unitsRes => {
    mapUnits = Array.isArray(unitsRes) ? unitsRes : (unitsRes.items || []);
    return api.get(`/api/realestate/buildings?project_id=${mapProjectId}`);
  }).then(buildingsRes => {
    mapBuildings = Array.isArray(buildingsRes) ? buildingsRes : (buildingsRes.items || []);
    updateMapKPIs();
    const svg = generateMapSVG();
    container.innerHTML = svg;
    loading.style.display = 'none';
    attachUnitEvents();
  }).catch(e => {
    loading.style.display = 'none';
    toastError(e);
  });
}

// Make loadProjectMap globally accessible
window.loadProjectMap = loadProjectMap;