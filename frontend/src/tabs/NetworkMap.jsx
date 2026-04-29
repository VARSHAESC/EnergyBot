import { useEffect, useState, useCallback, useMemo } from 'react';
import {
    MapContainer, TileLayer, GeoJSON, Marker, Popup,
    useMap, Polyline, Tooltip
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { useApp } from '../context/AppContext';
import { useLanguage } from '../context/LanguageContext';
import MarkerClusterGroup from 'react-leaflet-cluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import StreetView3D from '../components/3d/StreetView3D';
import { API_BASE } from '../lib/api';
import './NetworkMap.css';

/* ─── House-shaped marker icons ──────────────────────────────────────────────── */
const makeHouseIcon = (color, size = 20) => {
    const w = size;
    const h = Math.round(size * 1.3);
    return L.divIcon({
        className: '',
        html: `<svg width="${w}" height="${h}" viewBox="0 0 20 26" xmlns="http://www.w3.org/2000/svg" style="filter:drop-shadow(0 0 5px ${color}bb)">
            <path d="M10 1.5L19.5 9.5V25H13V17H7V25H0.5V9.5L10 1.5Z" fill="${color}" stroke="rgba(255,255,255,0.85)" stroke-width="1.4" stroke-linejoin="round"/>
            <rect x="7.5" y="17" width="5" height="8" fill="rgba(0,0,0,0.25)" rx="1"/>
        </svg>`,
        iconSize:    [w, h],
        iconAnchor:  [w / 2, h],
        popupAnchor: [0, -h],
    });
};

const ICONS = {
    red:    makeHouseIcon('#ef4444', 22),
    orange: makeHouseIcon('#f97316', 20),
    yellow: makeHouseIcon('#eab308', 20),
    blue:   makeHouseIcon('#3b82f6', 20),
};

const getMarkerIcon = (asset) => {
    if (asset.Risiko === 'Hoch')   return ICONS.red;
    if (asset.Risiko === 'Mittel') return ICONS.orange;
    return asset.Sparte === 'Gas'  ? ICONS.yellow : ICONS.blue;
};

/* ─── OSRM road routing – routes only between GeoJSON pipeline waypoints ──────
   Routes are requested in parallel; each falls back to a straight line on error.
   This avoids the building-interception issue (we never route to asset addresses).
   ─────────────────────────────────────────────────────────────────────────────── */
async function fetchRoutedPipelines(geoData, activeUtility) {
    if (!geoData?.features) return { gas: [], water: [] };

    const tasks = [];
    for (const feat of geoData.features) {
        const { utility, type } = feat.properties || {};
        if (type === 'Connection Hub') continue;
        if (activeUtility !== 'Alle Sparten' && utility !== activeUtility) continue;
        const geom = feat.geometry;
        if (!geom) continue;

        const segs = geom.type === 'LineString'      ? [geom.coordinates]
                   : geom.type === 'MultiLineString' ? geom.coordinates
                   : [];
        for (const coords of segs) {
            if (coords.length >= 2)
                tasks.push({ kind: utility === 'Gas' ? 'gas' : 'water', coords });
        }
    }

    const routeOne = async ({ kind, coords }) => {
        const straight = coords.map(([lon, lat]) => [lat, lon]);
        try {
            // Subsample to ≤10 waypoints so we stay within OSRM free-tier limits
            let wps = coords;
            if (coords.length > 10) {
                const step = (coords.length - 1) / 9;
                wps = Array.from({ length: 10 }, (_, i) => coords[Math.round(i * step)]);
            }
            const coordStr = wps.map(([lon, lat]) => `${lon},${lat}`).join(';');
            const ctrl = new AbortController();
            const tid  = setTimeout(() => ctrl.abort(), 4000);
            const res  = await fetch(
                `https://router.project-osrm.org/route/v1/driving/${coordStr}?overview=full&geometries=geojson`,
                { signal: ctrl.signal }
            );
            clearTimeout(tid);
            if (!res.ok) return { kind, line: straight };
            const data = await res.json();
            if (data.routes?.[0]?.geometry?.coordinates?.length) {
                return { kind, line: data.routes[0].geometry.coordinates.map(([lon, lat]) => [lat, lon]) };
            }
        } catch { /* timeout or network error → fall through */ }
        return { kind, line: straight };
    };

    // Cap at 40 segments to avoid hammering the free OSRM server
    const results = await Promise.all(tasks.slice(0, 40).map(routeOne));
    return {
        gas:   results.filter(r => r.kind === 'gas').map(r => r.line),
        water: results.filter(r => r.kind === 'water').map(r => r.line),
    };
}

/* ─── Pipeline renderer ──────────────────────────────────────────────────────── */
function PipelineLayer({ gas, water }) {
    return (
        <>
            {gas.map((line, i) => (
                <Polyline key={`gas-${i}`} positions={line}
                    pathOptions={{ color: '#fbbf24', weight: 3.5, opacity: 0.92, dashArray: '10 5', lineCap: 'round', lineJoin: 'round' }}>
                    <Tooltip sticky className="pipe-tooltip gas-tooltip">⛽ Gas Main Line</Tooltip>
                </Polyline>
            ))}
            {water.map((line, i) => (
                <Polyline key={`water-${i}`} positions={line}
                    pathOptions={{ color: '#60a5fa', weight: 3.5, opacity: 0.92, dashArray: '10 5', lineCap: 'round', lineJoin: 'round' }}>
                    <Tooltip sticky className="pipe-tooltip water-tooltip">💧 Water Main Line</Tooltip>
                </Polyline>
            ))}
        </>
    );
}

/* ─── Forces Leaflet to recalculate size after tab mount ────────────────────── */
function MapResizer() {
    const map = useMap();
    useEffect(() => {
        map.invalidateSize();
        const t = setTimeout(() => map.invalidateSize(), 300);
        return () => clearTimeout(t);
    }, [map]);
    return null;
}

/* ─── Map fly-to helper ──────────────────────────────────────────────────────── */
function MapFocuser({ center, zoom }) {
    const map = useMap();
    useEffect(() => {
        if (center) map.flyTo(center, zoom || 17, { duration: 1.2, easeLinearity: 0.25 });
    }, [center, zoom, map]);
    return null;
}

/* ─── Filter helper ──────────────────────────────────────────────────────────── */
function applyFilter(assets, filterConfig) {
    if (!filterConfig) return assets;
    return assets.filter(a => {
        if (filterConfig.risiko    && a.Risiko    !== filterConfig.risiko)    return false;
        if (filterConfig.sparte    && a.Sparte    !== filterConfig.sparte)    return false;
        if (filterConfig.werkstoff && a.Werkstoff !== filterConfig.werkstoff) return false;
        if (filterConfig.ageMin    && (a.Alter || 0) < filterConfig.ageMin)   return false;
        if (filterConfig.overLifespan) {
            const r = a['Erneuerung_empfohlen_bis'];
            if (!r || r >= 2026) return false;
        }
        if (filterConfig.unsuitable && !a['Infrastruktur_ungeeignet']) return false;
        return true;
    });
}

/* ─── Risk badge component ───────────────────────────────────────────────────── */
function RiskBadge({ risk, t }) {
    const cls   = { Hoch: 'high', Mittel: 'medium', Niedrig: 'low' }[risk] || 'unknown';
    const label = {
        Hoch: `⚠ ${t('mapExplorer.riskLabels.high')}`,
        Mittel: `◈ ${t('mapExplorer.riskLabels.medium')}`,
        Niedrig: `✓ ${t('mapExplorer.riskLabels.low')}`
    }[risk] || risk;
    return <span className={`nm-risk-badge ${cls}`}>{label}</span>;
}

/* ─── Module-level caches ────────────────────────────────────────────────────── */

// GeoJSON never changes — cache permanently for the session
let _geoCache = null;

// Assets keyed by utility — cache per session
const _assetCache = {};

/* ═══════════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════════════ */
export default function NetworkMap({ filterConfig }) {
    const { activeUtility, selectedAsset, setSelectedAsset } = useApp();
    const { t, lang } = useLanguage();
    const [geoData,         setGeoData]        = useState(_geoCache);
    const [mapFocus,        setMapFocus]        = useState(null);
    const [assets,          setAssets]          = useState(() => _assetCache[activeUtility] || []);
    const [viewMode,        setViewMode]        = useState('2D');
    const [hoveredAsset,    setHoveredAsset]    = useState(null);
    const [routedPipelines, setRoutedPipelines] = useState({ gas: [], water: [] });

    useEffect(() => {
        if (selectedAsset?.lat && selectedAsset?.lon)
            setMapFocus([selectedAsset.lat, selectedAsset.lon]);
    }, [selectedAsset]);

    // GeoJSON: fetch once per session, then serve from cache
    useEffect(() => {
        if (_geoCache) { setGeoData(_geoCache); return; }
        fetch('/data/utility_networks.geojson')
            .then(r => r.json())
            .then(d => { _geoCache = d; setGeoData(d); })
            .catch(e => console.error('GeoJSON:', e));
    }, []);

    // Assets: serve from cache instantly, fetch only on first visit per utility
    useEffect(() => {
        if (_assetCache[activeUtility]) {
            setAssets(_assetCache[activeUtility]);
            return;
        }
        fetch(`${API_BASE}/api/assets?utility=${activeUtility}`)
            .then(r => r.json())
            .then(d => {
                const records = d.records || [];
                _assetCache[activeUtility] = records;
                setAssets(records);
            })
            .catch(e => console.error('Assets:', e));
    }, [activeUtility]);

    // Fetch road-snapped pipeline routes whenever base data changes
    useEffect(() => {
        if (!geoData) return;
        let cancelled = false;
        fetchRoutedPipelines(geoData, activeUtility).then(result => {
            if (!cancelled) setRoutedPipelines(result);
        });
        return () => { cancelled = true; };
    }, [geoData, activeUtility]);

    const visibleAssets = useMemo(() => applyFilter(assets, filterConfig), [assets, filterConfig]);

    const handleAssetClick = useCallback((asset) => {
        setSelectedAsset(asset);
        setMapFocus([asset.lat, asset.lon]);
    }, [setSelectedAsset]);

    const handleReset = useCallback(() => {
        setSelectedAsset(null);
        setViewMode('2D');
        setMapFocus([51.246, 7.039]);
    }, [setSelectedAsset]);

    const hubPointToLayer = useCallback((feature, latlng) => {
        const { utility, type } = feature.properties || {};
        if (type !== 'Connection Hub') return null;
        if (activeUtility !== 'Alle Sparten' && utility !== activeUtility) return null;
        const color = utility === 'Gas' ? '#fbbf24' : '#60a5fa';
        return L.marker(latlng, {
            icon: L.divIcon({
                className: '',
                html: `<div style="width:8px;height:8px;background:${color};border:1.5px solid #0d0d14;transform:rotate(45deg);box-shadow:0 0 6px ${color}99"></div>`,
                iconSize: [12, 12], iconAnchor: [6, 6],
            }),
        });
    }, [activeUtility]);

    return (
        <div className="nm-root tab-pane">

            {filterConfig && (
                <div className="nm-filter-banner">
                    <span className="nm-filter-label">
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                            <path d="M1 2h10M3 6h6M5 10h2" stroke="#fbbf24" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                        {filterConfig.labelKey ? t(filterConfig.labelKey) : (filterConfig.label ?? 'Filtered View')}
                    </span>
                    <span className="nm-filter-count">{visibleAssets.length} {t('pages.anschluesse.breadcrumb')}</span>
                </div>
            )}

            <div className="nm-topbar">
                <div className="nm-title">
                    <div className="nm-title-dot" />
                    <span>{t('mapExplorer.title').toUpperCase()} — {activeUtility.toUpperCase()}</span>
                </div>

                <div className="nm-focus-info">
                    {selectedAsset ? (
                        <>
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <circle cx="6" cy="5" r="2.5" stroke="#22d3ee" strokeWidth="1.2"/>
                                <path d="M6 8c-2.5 0-4 1.5-4 1.5" stroke="#22d3ee" strokeWidth="1.2" strokeLinecap="round"/>
                            </svg>
                            <strong>{selectedAsset.Kundenname}</strong>
                            <span>·</span>
                            <span>{selectedAsset['Straße']} {selectedAsset.Hausnummer}</span>
                        </>
                    ) : (
                        <>
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <path d="M1 5.5H11M5.5 1V10" stroke="#64748b" strokeWidth="1.2" strokeLinecap="round"/>
                            </svg>
                            <span>Wülfrath Overview</span>
                            {!filterConfig && <span>— {assets.length} {t('common.totalConnections').toLowerCase()}</span>}
                        </>
                    )}
                </div>

                <div className="nm-btn-group">
                    {selectedAsset ? (
                        <>
                            <button
                                className={`nm-btn${viewMode === '2D' ? ' active' : ''}`}
                                onClick={() => setViewMode('2D')}>
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                    <rect x="1" y="1" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2"/>
                                    <path d="M1 4h10M4 4v7" stroke="currentColor" strokeWidth="1.2"/>
                                </svg>
                                2D Map
                            </button>
                            <button
                                className={`nm-btn${viewMode === '3D' ? ' active' : ''}`}
                                onClick={() => setViewMode('3D')}>
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                    <path d="M6 1L11 4v4L6 11 1 8V4L6 1Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                                </svg>
                                3D View
                            </button>
                            <button className="nm-btn danger" onClick={handleReset}>
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                    <path d="M6 2a4 4 0 1 0 4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                                    <path d="M10 2v4h-4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                                {t('nav.overview')}
                            </button>
                        </>
                    ) : (
                        <button className="nm-btn" onClick={() => setMapFocus([51.246, 7.039])}>
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.2"/>
                                <circle cx="6" cy="6" r="1.5" fill="currentColor"/>
                            </svg>
                            Center
                        </button>
                    )}
                </div>
            </div>

            <div className="nm-canvas">

                {selectedAsset && (
                    <div className="nm-asset-panel">
                        <div className="nm-asset-name">{selectedAsset.Kundenname}</div>
                        <div className="nm-asset-addr">
                            {selectedAsset['Straße']} {selectedAsset.Hausnummer}
                        </div>
                        {[
                            [t('mapExplorer.details.utility'),  selectedAsset.Sparte],
                            [t('mapExplorer.details.material'), selectedAsset.Werkstoff || '—'],
                            [t('mapExplorer.details.age'),      selectedAsset.Alter ? `${selectedAsset.Alter} yrs.` : '—'],
                        ].map(([k, v]) => (
                            <div className="nm-asset-row" key={k}>
                                <span className="nm-asset-key">{k}</span>
                                <span className="nm-asset-val">{v}</span>
                            </div>
                        ))}
                        <div className="nm-asset-row">
                            <span className="nm-asset-key">{t('mapExplorer.details.risk')}</span>
                            <RiskBadge risk={selectedAsset.Risiko} t={t} />
                        </div>
                    </div>
                )}

                {!selectedAsset && (
                    <div className="nm-stats">
                        <div className="nm-stat-pill">
                            <div className="nm-stat-dot nm-stat-dot--gas" />
                            <strong>{assets.filter(a => a.Sparte === 'Gas').length}</strong>
                            <span>{t('sidebar.gas')}</span>
                        </div>
                        <div className="nm-stat-pill">
                            <div className="nm-stat-dot nm-stat-dot--water" />
                            <strong>{assets.filter(a => a.Sparte !== 'Gas').length}</strong>
                            <span>{t('sidebar.water')}</span>
                        </div>
                        <div className="nm-stat-pill">
                            <div className="nm-stat-dot nm-stat-dot--risk" />
                            <strong>{assets.filter(a => a.Risiko === 'Hoch').length}</strong>
                            <span>{t('common.highRisk')}</span>
                        </div>
                    </div>
                )}

                <div className="nm-legend">
                    <div className="nm-legend-title">Legend</div>
                    <div className="nm-legend-row">
                        <div className="nm-legend-line nm-legend-line--gas" />
                        <span>{t('mapExplorer.legend.gasPipeline')}</span>
                    </div>
                    <div className="nm-legend-row">
                        <div className="nm-legend-line nm-legend-line--water" />
                        <span>{t('mapExplorer.legend.waterPipeline')}</span>
                    </div>
                    <div className="nm-legend-divider" />
                    <div className="nm-legend-row">
                        <svg width="13" height="16" viewBox="0 0 20 26" fill="none" className="nm-legend-house">
                            <path d="M10 1.5L19.5 9.5V25H13V17H7V25H0.5V9.5L10 1.5Z" fill="#ef4444" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" strokeLinejoin="round"/>
                        </svg>
                        <span>{t('common.highRisk')}</span>
                    </div>
                    <div className="nm-legend-row">
                        <svg width="13" height="16" viewBox="0 0 20 26" fill="none" className="nm-legend-house">
                            <path d="M10 1.5L19.5 9.5V25H13V17H7V25H0.5V9.5L10 1.5Z" fill="#f97316" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" strokeLinejoin="round"/>
                        </svg>
                        <span>{t('common.mediumRisk')}</span>
                    </div>
                    <div className="nm-legend-row">
                        <svg width="13" height="16" viewBox="0 0 20 26" fill="none" className="nm-legend-house">
                            <path d="M10 1.5L19.5 9.5V25H13V17H7V25H0.5V9.5L10 1.5Z" fill="#eab308" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" strokeLinejoin="round"/>
                        </svg>
                        <span>{t('mapExplorer.legend.gasConnection')}</span>
                    </div>
                    <div className="nm-legend-row">
                        <svg width="13" height="16" viewBox="0 0 20 26" fill="none" className="nm-legend-house">
                            <path d="M10 1.5L19.5 9.5V25H13V17H7V25H0.5V9.5L10 1.5Z" fill="#3b82f6" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" strokeLinejoin="round"/>
                        </svg>
                        <span>{t('mapExplorer.legend.waterConnection')}</span>
                    </div>
                </div>

                {viewMode === '3D' && selectedAsset ? (
                    <StreetView3D asset={selectedAsset} utility={activeUtility} />
                ) : (
                    <MapContainer
                        center={[51.246, 7.039]}
                        zoom={15}
                        style={{ height: '100%', width: '100%' }}
                        zoomControl>

                        <TileLayer
                            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>'
                            subdomains="abcd"
                            maxZoom={20}
                            keepBuffer={4}
                        />

                        <MapResizer />

                        <PipelineLayer gas={routedPipelines.gas} water={routedPipelines.water} />

                        {geoData && (
                            <GeoJSON
                                key={`hubs-${activeUtility}`}
                                data={geoData}
                                style={() => ({ opacity: 0, fillOpacity: 0, weight: 0 })}
                                pointToLayer={hubPointToLayer}
                            />
                        )}

                        <MapFocuser center={mapFocus} zoom={selectedAsset ? 17 : 15} />

                        <MarkerClusterGroup chunkedLoading polygonOptions={{ opacity: 0 }}>
                            {visibleAssets.map((asset, idx) => {
                                if (!asset.lat || !asset.lon) return null;
                                return (
                                    <Marker
                                        key={idx}
                                        position={[asset.lat, asset.lon]}
                                        icon={getMarkerIcon(asset)}
                                        eventHandlers={{
                                            click:     () => handleAssetClick(asset),
                                            mouseover: () => setHoveredAsset(asset),
                                            mouseout:  () => setHoveredAsset(null),
                                        }}>
                                        <Popup>
                                            <div className="nm-popup">
                                                <div className="nm-popup-name">
                                                    {asset.Kundenname || 'Asset'}
                                                </div>
                                                <div className="nm-popup-addr">
                                                    {asset['Straße']} {asset.Hausnummer}
                                                </div>
                                                {[
                                                    ['Utility',  asset.Sparte],
                                                    ['Age',      asset.Alter ? `${asset.Alter} years` : '—'],
                                                    ['Material', asset.Werkstoff || '—'],
                                                ].map(([k, v]) => (
                                                    <div className="nm-popup-row" key={k}>
                                                        <span className="nm-popup-key">{k}</span>
                                                        <span className="nm-popup-val">{v}</span>
                                                    </div>
                                                ))}
                                                <div className="nm-popup-risk-row">
                                                    <span className="nm-popup-key">Risk</span>
                                                    <RiskBadge risk={asset.Risiko} />
                                                </div>
                                                <button
                                                    className="nm-popup-btn"
                                                    onClick={() => handleAssetClick(asset)}>
                                                    View details →
                                                </button>
                                            </div>
                                        </Popup>
                                    </Marker>
                                );
                            })}
                        </MarkerClusterGroup>
                    </MapContainer>
                )}
            </div>
        </div>
    );
}
