import { useEffect, useState, useMemo, useCallback, useRef, Fragment } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, CircleMarker, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import MarkerClusterGroup from 'react-leaflet-cluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import { useApp } from '../context/AppContext';
import { useLanguage } from '../context/LanguageContext';
import { API_BASE } from '../lib/api';
import { X, Map as MapIcon, RotateCcw, ChevronDown, AlertTriangle, Clock, Droplets, Flame, Wrench, GitBranch, Activity } from 'lucide-react';
import './MapExplorerPage.css';

/* ─── Map helpers ─────────────────────────────────────────────────────────── */
function AutoFit({ records }) {
    const map = useMap();
    const doneRef = useRef(false);
    useEffect(() => {
        if (doneRef.current || records.length === 0) return;
        const pts = records.filter(r => r.lat && r.lon).map(r => [r.lat, r.lon]);
        if (pts.length > 0) {
            try { map.fitBounds(pts, { padding: [40, 40], maxZoom: 16 }); doneRef.current = true; }
            catch (_) { }
        }
    }, [records.length, map]);
    return null;
}

function MapResizer() {
    const map = useMap();
    useEffect(() => {
        map.invalidateSize();
        const t = setTimeout(() => map.invalidateSize(), 300);
        return () => clearTimeout(t);
    }, [map]);
    return null;
}

/* ─── Colours ─────────────────────────────────────────────────────────────── */
const RISK_COLOR = { Hoch: '#ef4444', Mittel: '#f97316', Niedrig: '#22c55e' };
const SPARTE_COLOR = { Gas: '#f59e0b', Wasser: '#38bdf8' };

function getMarkerColor(asset, colorBy) {
    if (colorBy === 'risiko') return RISK_COLOR[asset.Risiko] ?? '#888';
    if (colorBy === 'sparte') return SPARTE_COLOR[asset.Sparte] ?? '#888';
    if (colorBy === 'lifespan') return asset.over_lifespan ? '#f59e0b' : '#22c55e';
    if (colorBy === 'age') {
        const a = asset.Alter || 0;
        if (a >= 80) return '#ef4444';
        if (a >= 60) return '#f97316';
        if (a >= 40) return '#f59e0b';
        return '#22c55e';
    }
    return '#888';
}

/* ─── Filter options ──────────────────────────────────────────────────────── */
const WERKSTOFF_OPTS = ['Alle', 'Stahl', 'PE', 'PVC', 'Asbestzement-(AZ)', 'Stahl mit KKS', 'Stahl ohne KKS'];
const AGE_OPTS = [
    { labelKey: 'mapExplorer.allAges', min: 0 },
    { label: '> 20 yrs', min: 20 },
    { label: '> 40 yrs', min: 40 },
    { label: '> 60 yrs', min: 60 },
    { label: '> 80 yrs', min: 80 },
];
const COLOR_BY_OPTS = [
    { value: 'risiko', labelKey: 'mapExplorer.colorOptions.risiko' },
    { value: 'sparte', labelKey: 'mapExplorer.colorOptions.sparte' },
    { value: 'lifespan', labelKey: 'mapExplorer.colorOptions.lifespan' },
    { value: 'age', labelKey: 'mapExplorer.colorOptions.age' },
];

/* ─── Popup ───────────────────────────────────────────────────────────────── */
function AssetPopup({ asset }) {
    const { t } = useLanguage();
    return (
        <Popup className="explorer-popup">
            <div className="ep-header">
                <span className="ep-sparte" style={{
                    background: (SPARTE_COLOR[asset.Sparte] ?? '#888') + '22',
                    color: SPARTE_COLOR[asset.Sparte] ?? '#888',
                    borderColor: (SPARTE_COLOR[asset.Sparte] ?? '#888') + '44',
                }}>
                    {asset.Sparte === 'Gas' ? '⛽' : '💧'} {asset.Sparte}
                </span>
                <span className="ep-risk" style={{ color: RISK_COLOR[asset.Risiko] }}>
                    {asset.Risiko}
                </span>
            </div>
            <div className="ep-name">{asset.Kundenname || '—'}</div>
            <div className="ep-addr">{asset['Straße']} {asset.Hausnummer}</div>
            <div className="ep-stats">
                <div><span>{t('mapExplorer.details.age')}</span><strong>{asset.Alter ? `${asset.Alter} yrs` : '—'}</strong></div>
                <div><span>{t('mapExplorer.details.material')}</span><strong>{asset.Werkstoff || '—'}</strong></div>
                <div><span>{t('mapExplorer.details.renewalBy')}</span><strong>{asset['Erneuerung_empfohlen_bis'] || '—'}</strong></div>
            </div>
        </Popup>
    );
}

/* ─── Markers ─────────────────────────────────────────────────────────────── */
function AssetDot({ asset, colorBy, onClick }) {
    if (!asset.lat || !asset.lon) return null;
    const color = getMarkerColor(asset, colorBy);
    return (
        <CircleMarker
            center={[asset.lat, asset.lon]}
            radius={5}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.9, weight: 1.5, opacity: 1 }}
            eventHandlers={{ click: () => onClick(asset) }}
        >
            <AssetPopup asset={asset} />
        </CircleMarker>
    );
}

function HouseMarker({ asset, colorBy, onClick, showNum }) {
    if (!asset.lat || !asset.lon) return null;
    const color = getMarkerColor(asset, colorBy);
    const num = asset.Hausnummer || '?';
    const icon = useMemo(() => L.divIcon({
        html: `<div class="explorer-house-pin" style="--c:${color}">
            ${showNum ? `<div class="pin-num-top">${num}</div>` : ''}
            <svg viewBox="0 0 24 24" class="pin-home-svg" fill="${color}">
                <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
            </svg>
        </div>`,
        className: '',
        iconSize: [32, 44],
        iconAnchor: [16, 44],
        popupAnchor: [0, -46],
    }), [color, num, showNum]);

    return (
        <Marker position={[asset.lat, asset.lon]} icon={icon} eventHandlers={{ click: () => onClick(asset) }}>
            <AssetPopup asset={asset} />
        </Marker>
    );
}

function MarkerLayer({ filtered, colorBy, onDotClick }) {
    const map = useMap();
    const [zoom, setZoom] = useState(() => map.getZoom());
    useEffect(() => {
        const h = () => setZoom(map.getZoom());
        map.on('zoomend', h);
        return () => map.off('zoomend', h);
    }, [map]);

    return (
        <MarkerClusterGroup
            chunkedLoading
            maxClusterRadius={40}
            polygonOptions={{ opacity: 0 }}
            iconCreateFunction={(cluster) => {
                const count = cluster.getChildCount();
                const size = count > 100 ? 48 : count > 30 ? 40 : 32;
                return L.divIcon({
                    html: `<div class="explorer-cluster" style="width:${size}px;height:${size}px;font-size:${size < 40 ? '0.72rem' : '0.8rem'}">${count}</div>`,
                    className: '',
                    iconSize: [size, size],
                    iconAnchor: [size / 2, size / 2],
                });
            }}
        >
            {filtered.map((asset, i) =>
                zoom >= 17
                    ? <HouseMarker key={i} asset={asset} colorBy={colorBy} onClick={onDotClick} showNum={zoom >= 16} />
                    : <AssetDot key={i} asset={asset} colorBy={colorBy} onClick={onDotClick} />
            )}
        </MarkerClusterGroup>
    );
}

/* ══════════════════════════════════════════════════════════════════════════
   PIPELINE SYSTEM
   ══════════════════════════════════════════════════════════════════════════

   Approach:
   1. ONE Overpass query fetches all named roads in the Wülfrath bbox.
      Cached as a module-level singleton — only fetches once per session.
   2. Assets grouped by street name, then proximity-clustered at 300m so
      the same street name in different villages never connects (e.g.
      Jahnstraße appears in 3 villages 6.5km apart).
   3. For each cluster: find OSM way polylines that pass within 200m of
      any asset → draw the whole way as the pipeline.
   4. Gas offset +3m right, Water -3m left → side-by-side on the road.
   5. Connection stubs (dashed) connect each house to the nearest road.

   200m threshold (not 120m):
   Assets sit inside buildings, often 80-150m from the road centreline.
   200m catches all of them without pulling in unrelated streets.
   ══════════════════════════════════════════════════════════════════════════ */

const OVERPASS_URL = 'https://overpass-api.de/api/interpreter';
const WULFRATH_BBOX = '51.220,6.900,51.350,7.140';

/* Singleton road cache — one fetch per browser session */
let _roadCachePromise = null;

function getRoadCache() {
    if (_roadCachePromise) return _roadCachePromise;
    const query = `[out:json][timeout:30];
way["highway"]["name"](${WULFRATH_BBOX});
(._;>;);
out body;`;
    _roadCachePromise = fetch(OVERPASS_URL, {
        method: 'POST',
        body: `data=${encodeURIComponent(query)}`,
    })
        .then(r => r.json())
        .then(data => {
            const nodes = {};
            data.elements.forEach(el => {
                if (el.type === 'node') nodes[el.id] = [el.lat, el.lon];
            });
            const byName = {};
            data.elements.forEach(el => {
                if (el.type !== 'way' || !el.tags?.name) return;
                const coords = (el.nodes || []).map(id => nodes[id]).filter(Boolean);
                if (coords.length >= 2) {
                    const name = el.tags.name;
                    (byName[name] = byName[name] || []).push(coords);
                }
            });
            console.log(`[Pipeline] road cache loaded: ${Object.keys(byName).length} streets`);
            return byName;
        })
        .catch(err => {
            console.error('[Pipeline] Overpass fetch failed:', err);
            _roadCachePromise = null; // allow retry on next attempt
            return {};
        });
    return _roadCachePromise;
}

/* ─── Geometry utilities ──────────────────────────────────────────────────── */

function distM(lat1, lon1, lat2, lon2) {
    const dLat = (lat2 - lat1) * 111320;
    const dLon = (lon2 - lon1) * 111320 * Math.cos(((lat1 + lat2) / 2) * Math.PI / 180);
    return Math.sqrt(dLat * dLat + dLon * dLon);
}

/* Split asset points into proximity clusters (max 300m gap). */
function proximityClusters(points, maxGapM = 300) {
    if (!points.length) return [];
    const sorted = [...points].sort((a, b) => a.lat !== b.lat ? a.lat - b.lat : a.lon - b.lon);
    const clusters = [[sorted[0]]];
    for (let i = 1; i < sorted.length; i++) {
        const pt = sorted[i];
        let bestCluster = clusters[0], bestDist = Infinity;
        for (const c of clusters) {
            for (const cp of c) {
                const d = distM(cp.lat, cp.lon, pt.lat, pt.lon);
                if (d < bestDist) { bestDist = d; bestCluster = c; }
            }
        }
        bestDist <= maxGapM ? bestCluster.push(pt) : clusters.push([pt]);
    }
    return clusters;
}

/*
 * Keep an entire OSM way if ANY of its nodes is within maxDistM of ANY
 * asset in the cluster. 200m threshold handles assets set back from roads.
 */
function waysNearCluster(roadPolylines, cluster, maxDistM = 200) {
    return roadPolylines.filter(way =>
        way.some(node =>
            cluster.some(asset =>
                distM(asset.lat, asset.lon, node[0], node[1]) <= maxDistM
            )
        )
    );
}

/*
 * For a single isolated asset, find the nearest road node and return a
 * short sub-segment (node ± 2 neighbours) of that way.
 */
function nearestSegment(roadPolylines, lat, lon, maxDistM = 200) {
    let bestWay = null, bestIdx = -1, bestDist = Infinity;
    roadPolylines.forEach(way => {
        way.forEach((node, idx) => {
            const d = distM(lat, lon, node[0], node[1]);
            if (d < bestDist) { bestDist = d; bestWay = way; bestIdx = idx; }
        });
    });
    if (!bestWay || bestDist > maxDistM) return null;
    const from = Math.max(0, bestIdx - 2);
    const to = Math.min(bestWay.length - 1, bestIdx + 2);
    return bestWay.slice(from, to + 1);
}

/* Apply lateral offset so Gas and Water lines appear side-by-side. */
function applyLateralOffset(coords, offsetMetres) {
    if (Math.abs(offsetMetres) < 0.01 || coords.length < 2) return coords;
    const DEG_PER_M = 1 / 111320;
    return coords.map((pt, i) => {
        const prev = coords[Math.max(0, i - 1)];
        const next = coords[Math.min(coords.length - 1, i + 1)];
        const dLat = next[0] - prev[0];
        const dLon = next[1] - prev[1];
        const len = Math.sqrt(dLat * dLat + dLon * dLon) || 1;
        return [
            pt[0] + (-dLon / len) * offsetMetres * DEG_PER_M,
            pt[1] + (dLat / len) * offsetMetres * DEG_PER_M / Math.cos(pt[0] * Math.PI / 180),
        ];
    });
}

/* Find the nearest point on any road polyline to a given coordinate. */
function nearestPointOnRoads(roadPolylines, lat, lon) {
    let best = null, bestDist = Infinity;
    roadPolylines.forEach(way => {
        way.forEach(node => {
            const d = distM(lat, lon, node[0], node[1]);
            if (d < bestDist) { bestDist = d; best = node; }
        });
    });
    return best ? { pt: best, dist: bestDist } : null;
}

/*
 * After building all polylines for a utility, scan every pair of endpoint
 * combos. If two line endings are within maxGapM metres (OSM ways typically
 * split at intersections leaving a 1-30m gap), add a short connector so the
 * network looks continuous rather than broken.
 */
function stitchEndpoints(lines, maxGapM = 40) {
    if (lines.length < 2) return lines;
    const connectors = [];
    for (let i = 0; i < lines.length; i++) {
        const a = lines[i];
        const aS = a.coords[0];
        const aE = a.coords[a.coords.length - 1];
        for (let j = i + 1; j < lines.length; j++) {
            const b = lines[j];
            if (a.color !== b.color) continue;
            const bS = b.coords[0];
            const bE = b.coords[b.coords.length - 1];
            let closest = Infinity, bestPair = null;
            for (const [p, q] of [[aE, bS], [aE, bE], [aS, bS], [aS, bE]]) {
                const d = distM(p[0], p[1], q[0], q[1]);
                if (d > 0.5 && d < closest) { closest = d; bestPair = [p, q]; }
            }
            if (bestPair && closest <= maxGapM) {
                connectors.push({ coords: bestPair, color: a.color, weight: a.weight, opacity: a.opacity * 0.8 });
            }
        }
    }
    return [...lines, ...connectors];
}

/* ─── Connection stub layer (house → nearest road, zoom ≥ 15) ────────────── */
function StubLayer({ assets, roadPolylines, sparte, show }) {
    const map = useMap();
    const [zoom, setZoom] = useState(() => map.getZoom());
    useEffect(() => {
        const h = () => setZoom(map.getZoom());
        map.on('zoomend', h);
        return () => map.off('zoomend', h);
    }, [map]);

    const isVisible = show === 'alle' ||
        (show === 'gas' && sparte === 'Gas') ||
        (show === 'wasser' && sparte === 'Wasser');

    if (!isVisible || zoom < 15 || !roadPolylines.length) return null;

    const color = SPARTE_COLOR[sparte];
    return (
        <>
            {assets
                .filter(a => a.Sparte === sparte && a.lat && a.lon)
                .map((asset, i) => {
                    const found = nearestPointOnRoads(roadPolylines, asset.lat, asset.lon);
                    if (!found || found.dist > 60) return null;
                    return (
                        <Polyline key={i}
                            positions={[[asset.lat, asset.lon], found.pt]}
                            pathOptions={{
                                color,
                                weight: 1,
                                opacity: 0.45,
                                dashArray: '3 5',
                                lineCap: 'round',
                            }}
                        />
                    );
                })}
        </>
    );
}

/* ─── Source supply node ──────────────────────────────────────────────────── */
function SourceLayer({ allRecords, lines, show }) {
    const { t } = useLanguage();
    if (!show || show === 'off') return null;

    const spartes = show === 'alle' ? ['Gas', 'Wasser']
        : show === 'gas' ? ['Gas'] : ['Wasser'];

    const items = spartes.map(sparte => {
        const assets = allRecords.filter(a => a.Sparte === sparte && a.lat && a.lon);
        if (!assets.length) return null;
        const color = SPARTE_COLOR[sparte];
        const lat = assets.reduce((s, a) => s + a.lat, 0) / assets.length;
        const lon = assets.reduce((s, a) => s + a.lon, 0) / assets.length;

        // Find nearest pipeline point → used for dashed trunk line
        const sparteLines = lines.filter(l => l.color === color);
        let trunkPt = null, trunkDist = Infinity;
        sparteLines.forEach(line =>
            line.coords.forEach(pt => {
                const d = distM(lat, lon, pt[0], pt[1]);
                if (d < trunkDist) { trunkDist = d; trunkPt = pt; }
            })
        );
        return { pos: [lat, lon], sparte, count: assets.length, color, trunkPt };
    }).filter(Boolean);

    if (!items.length) return null;

    return (
        <>
            {items.map(({ pos, sparte, count, color, trunkPt }) => {
                const icon = L.divIcon({
                    html: `<div class="src-node" style="--c:${color}">
                        <div class="src-pulse"></div>
                        <div class="src-ring"></div>
                        <div class="src-inner">
                            ${sparte === 'Gas'
                            ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="${color}"><path d="M13 2.05v2.02c3.95.49 7 3.85 7 7.93 0 3.21-1.81 6-4.72 7.28L13 17v5h6l-2.23-2.23C19.91 18.07 22 15.14 22 12c0-5.18-3.95-9.45-9-9.95M11 2.05C5.95 2.55 2 6.82 2 12c0 3.14 2.09 6.07 5.23 7.77L5 22h6v-5l-2.28 2.28C6.81 18 5 15.21 5 12c0-4.08 3.05-7.44 7-7.93V2.05z"/></svg>`
                            : `<svg width="16" height="16" viewBox="0 0 24 24" fill="${color}"><path d="M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8z"/></svg>`
                        }
                            <div class="src-count">${count}</div>
                        </div>
                        <div class="src-label">${sparte === 'Gas' ? t('mapExplorer.supplyNode.gasSupply') : t('mapExplorer.supplyNode.waterSupply')}</div>
                    </div>`,
                    className: '',
                    iconSize: [80, 74],
                    iconAnchor: [40, 37],
                    popupAnchor: [0, -44],
                });
                return (
                    <Fragment key={sparte}>
                        {trunkPt && (
                            <Polyline
                                positions={[pos, trunkPt]}
                                pathOptions={{ color, weight: 3.5, opacity: 0.55, dashArray: '10 6' }}
                            />
                        )}
                        <Marker position={pos} icon={icon} zIndexOffset={2000}>
                            <Popup className="explorer-popup">
                                <div style={{ padding: '12px 14px', minWidth: 170 }}>
                                    <div style={{ color, fontWeight: 700, fontSize: '0.8rem', marginBottom: 6 }}>
                                        {sparte === 'Gas' ? t('mapExplorer.supplyNode.gasNode') : t('mapExplorer.supplyNode.waterNode')}
                                    </div>
                                    <div style={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.67rem', lineHeight: 1.6 }}>
                                        {t('mapExplorer.supplyNode.distributionPoint')}<br />
                                        {t('mapExplorer.supplyNode.serving').replace('{count}', `<strong>${count}</strong>`)}
                                    </div>
                                </div>
                            </Popup>
                        </Marker>
                    </Fragment>
                );
            })}
        </>
    );
}

/* ─── Pipeline layer ──────────────────────────────────────────────────────── */
function PipelineLayer({ allRecords, show }) {
    const [lines, setLines] = useState([]);
    const [roadPolys, setRoadPolys] = useState([]);
    const [cacheReady, setCacheReady] = useState(false);

    useEffect(() => {
        let cancelled = false;
        getRoadCache().then(cache => {
            if (!cancelled) {
                window.__stadtwerke_roads = cache;
                setCacheReady(true);
            }
        });
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        if (!cacheReady || !show || show === 'off') {
            setLines([]); setRoadPolys([]); return;
        }

        const cache = window.__stadtwerke_roads || {};
        const spartes = show === 'alle' ? ['Gas', 'Wasser'] : show === 'gas' ? ['Gas'] : ['Wasser'];

        const resultLines = [];
        const allRoadPolys = [];

        spartes.forEach(sparte => {
            const color = SPARTE_COLOR[sparte];
            const offsetM = sparte === 'Gas' ? 3 : -3;

            const byStreet = {};
            allRecords
                .filter(a => a.Sparte === sparte && a.lat && a.lon)
                .forEach(a => {
                    const street = (a['Straße'] || '').trim();
                    if (!street) return;
                    (byStreet[street] = byStreet[street] || []).push({ lat: a.lat, lon: a.lon });
                });

            Object.entries(byStreet).forEach(([streetName, pts]) => {
                const roadWays = cache[streetName];
                const clusters = proximityClusters(pts, 300);

                clusters.forEach(cluster => {
                    if (cluster.length === 1) {
                        if (roadWays?.length) {
                            const seg = nearestSegment(roadWays, cluster[0].lat, cluster[0].lon, 200);
                            if (seg?.length >= 2) {
                                resultLines.push({ coords: applyLateralOffset(seg, offsetM), color, weight: 2, opacity: 0.7 });
                                allRoadPolys.push(seg);
                                return;
                            }
                        }
                        // No road found for this isolated asset — skip rather than draw a random stub
                        return;
                    }

                    // Multi-asset cluster
                    if (roadWays?.length) {
                        const nearby = waysNearCluster(roadWays, cluster, 200);
                        if (nearby.length) {
                            nearby.forEach(way => {
                                resultLines.push({ coords: applyLateralOffset(way, offsetM), color, weight: 2, opacity: 0.85 });
                                allRoadPolys.push(way);
                            });
                            return;
                        }
                    }

                    // Fallback: no OSM road — short straight line within cluster bbox only
                    // (cluster is max 300m wide so this can't slash across the map)
                    const sorted = [...cluster].sort((a, b) => a.lat - b.lat);
                    const seg = [
                        [sorted[0].lat, sorted[0].lon],
                        [sorted[sorted.length - 1].lat, sorted[sorted.length - 1].lon],
                    ];
                    resultLines.push({ coords: applyLateralOffset(seg, offsetM), color, weight: 1.5, opacity: 0.45 });
                    allRoadPolys.push(seg);
                });
            });
        });

        const stitched = stitchEndpoints(resultLines, 40);
        setLines(stitched);
        setRoadPolys(allRoadPolys);
        console.log(`[Pipeline] built ${resultLines.length} raw + ${stitched.length - resultLines.length} stitched segments for show=${show}`);
    }, [cacheReady, show, allRecords]);

    const gasAssets = useMemo(() => allRecords.filter(a => a.Sparte === 'Gas'), [allRecords]);
    const wasserAssets = useMemo(() => allRecords.filter(a => a.Sparte === 'Wasser'), [allRecords]);

    if (show === 'off') return null;

    return (
        <>
            {lines.map((line, i) => (
                <Polyline key={i}
                    positions={line.coords}
                    pathOptions={{
                        color: line.color,
                        weight: line.weight,
                        opacity: line.opacity,
                        lineCap: 'round',
                        lineJoin: 'round',
                    }}
                />
            ))}
            {cacheReady && <SourceLayer allRecords={allRecords} lines={lines} show={show} />}
            <StubLayer assets={gasAssets} roadPolylines={roadPolys} sparte="Gas" show={show} />
            <StubLayer assets={wasserAssets} roadPolylines={roadPolys} sparte="Wasser" show={show} />
        </>
    );
}

/* ─── Module-level record cache (keyed by utility) ───────────────────────── */
const _explorerCache = {};

/* ─── Main component ─────────────────────────────────────────────────────── */
export default function MapExplorerPage() {
    const { activeUtility } = useApp();
    const { t, lang } = useLanguage();

    const [allRecords, setAllRecords] = useState(() => _explorerCache[activeUtility] || []);
    const [loading, setLoading] = useState(!_explorerCache[activeUtility]);
    const [selected, setSelected] = useState(null);
    const [panelOpen, setPanelOpen] = useState(false);

    const [fSparte, setFSparte] = useState('Alle');
    const [fRisiko, setFRisiko] = useState('Alle');
    const [fWerkstoff, setFWerkstoff] = useState('Alle');
    const [fAge, setFAge] = useState(0);
    const [fLifespan, setFLifespan] = useState(false);
    const [colorBy, setColorBy] = useState('risiko');
    const [fPipeline, setFPipeline] = useState('off');

    /* Prefetch road cache as soon as the page loads */
    useEffect(() => { getRoadCache(); }, []);

    useEffect(() => {
        if (_explorerCache[activeUtility]) {
            setAllRecords(_explorerCache[activeUtility]);
            setLoading(false);
            return;
        }
        setLoading(true);
        let cancelled = false;
        fetch(`${API_BASE}/api/map-explorer?utility=${activeUtility}`)
            .then(r => {
                if (!r.ok) throw new Error(`API error ${r.status}`);
                return r.json();
            })
            .then(d => {
                if (cancelled) return;
                const records = d.records || [];
                console.log(`[MapExplorer] loaded ${records.length} records for ${activeUtility}`);
                if (records.length === 0) console.warn('[MapExplorer] API returned 0 records — check backend');
                _explorerCache[activeUtility] = records;
                setAllRecords(records);
                setLoading(false);
            })
            .catch(err => {
                if (!cancelled) {
                    console.error('[MapExplorer] fetch failed:', err);
                    setLoading(false);
                }
            });
        return () => { cancelled = true; };
    }, [activeUtility]);

    const filtered = useMemo(() => allRecords.filter(a => {
        if (fSparte !== 'Alle' && a.Sparte !== fSparte) return false;
        if (fRisiko !== 'Alle' && a.Risiko !== fRisiko) return false;
        if (fWerkstoff !== 'Alle' && a.Werkstoff !== fWerkstoff) return false;
        if (fAge > 0 && (a.Alter || 0) < fAge) return false;
        if (fLifespan && !a.over_lifespan) return false;
        return true;
    }), [allRecords, fSparte, fRisiko, fWerkstoff, fAge, fLifespan]);

    const stats = useMemo(() => ({
        total: filtered.length,
        wasser: filtered.filter(a => a.Sparte === 'Wasser').length,
        gas: filtered.filter(a => a.Sparte === 'Gas').length,
        hoch: filtered.filter(a => a.Risiko === 'Hoch').length,
        mittel: filtered.filter(a => a.Risiko === 'Mittel').length,
        niedrig: filtered.filter(a => a.Risiko === 'Niedrig').length,
        over: filtered.filter(a => a.over_lifespan).length,
    }), [filtered]);

    const resetFilters = () => {
        setFSparte('Alle'); setFRisiko('Alle');
        setFWerkstoff('Alle'); setFAge(0); setFLifespan(false);
    };

    const handleDotClick = useCallback((asset) => {
        setSelected(asset); setPanelOpen(true);
    }, []);

    const activeFilterCount = [
        fSparte !== 'Alle', fRisiko !== 'Alle',
        fWerkstoff !== 'Alle', fAge > 0, fLifespan,
    ].filter(Boolean).length;

    const pipelineActive = fPipeline !== 'off';

    return (
        <div className="explorer-root">

            {/* ── Filter bar ─────────────────────────────────────────────── */}
            <div className="explorer-filterbar">
                <div className="efb-left">
                    <div className="efb-brand"><MapIcon size={14} /><span>{t('mapExplorer.brand')}</span></div>
                    {activeFilterCount > 0 && <span className="efb-active-badge">{activeFilterCount} {t('mapExplorer.activeFilters')}</span>}
                </div>
                <div className="efb-controls">
                    <div className="efb-select-wrap">
                        <select className="efb-select" value={fSparte} onChange={e => setFSparte(e.target.value)}>
                            <option value="Alle">{t('mapExplorer.allUtilities')}</option>
                            <option value="Gas">{t('sidebar.gas')}</option>
                            <option value="Wasser">{t('sidebar.water')}</option>
                        </select>
                        <ChevronDown size={11} className="efb-chevron" />
                    </div>
                    <div className="efb-select-wrap">
                        <select className="efb-select" value={fRisiko} onChange={e => setFRisiko(e.target.value)}>
                            <option value="Alle">{t('mapExplorer.allRisk')}</option>
                            <option value="Hoch">{t('mapExplorer.riskLabels.high')}</option>
                            <option value="Mittel">{t('mapExplorer.riskLabels.medium')}</option>
                            <option value="Niedrig">{t('mapExplorer.riskLabels.low')}</option>
                        </select>
                        <ChevronDown size={11} className="efb-chevron" />
                    </div>
                    <div className="efb-select-wrap">
                        <select className="efb-select" value={fWerkstoff} onChange={e => setFWerkstoff(e.target.value)}>
                            {WERKSTOFF_OPTS.map(w => (
                                <option key={w} value={w}>
                                    {w === 'Alle' ? t('mapExplorer.allMaterials') : w}
                                </option>
                            ))}
                        </select>
                        <ChevronDown size={11} className="efb-chevron" />
                    </div>
                    <div className="efb-select-wrap">
                        <select className="efb-select" value={fAge} onChange={e => setFAge(Number(e.target.value))}>
                            {AGE_OPTS.map(o => (
                                <option key={o.min} value={o.min}>
                                    {o.labelKey ? t(o.labelKey) : o.label}
                                </option>
                            ))}
                        </select>
                        <ChevronDown size={11} className="efb-chevron" />
                    </div>
                    <div className="efb-select-wrap">
                        <select className="efb-select efb-select--color" value={colorBy} onChange={e => setColorBy(e.target.value)}>
                            {COLOR_BY_OPTS.map(o => (
                                <option key={o.value} value={o.value}>
                                    {t('mapExplorer.colorBy')}{t(o.labelKey)}
                                </option>
                            ))}
                        </select>
                        <ChevronDown size={11} className="efb-chevron" />
                    </div>
                    <button className={`efb-toggle ${fLifespan ? 'efb-toggle--active' : ''}`}
                        onClick={() => setFLifespan(v => !v)}>
                        <Clock size={12} />{t('mapExplorer.overdueOnly')}
                    </button>
                    {activeFilterCount > 0 && (
                        <button className="efb-reset" onClick={resetFilters}><RotateCcw size={12} /></button>
                    )}
                    <div className="efb-sep" />
                    <div className={`efb-pipe-chip ${pipelineActive ? `efb-pipe-chip--on efb-pipe-chip--${fPipeline}` : ''}`}>
                        <GitBranch size={12} />
                        <span className="efb-pipe-label">{t('mapExplorer.pipelines')}</span>
                        <div className="efb-select-wrap">
                            <select className="efb-select efb-select--borderless" value={fPipeline}
                                onChange={e => setFPipeline(e.target.value)}>
                                <option value="off">{t('mapExplorer.none')}</option>
                                <option value="gas">Gas</option>
                                <option value="wasser">Water</option>
                                <option value="alle">{t('sidebar.allUtilities')}</option>
                            </select>
                            <ChevronDown size={11} className="efb-chevron" />
                        </div>
                    </div>
                </div>
                <div className="efb-count">
                    <Activity size={11} />
                    <span>{loading ? '…' : `${filtered.length} / ${allRecords.length}`}</span>
                </div>
            </div>

            {/* ── Stats strip ────────────────────────────────────────────── */}
            <div className="explorer-stats">
                <div className="estats-group">
                    {[
                        { label: t('common.totalConnections'), value: stats.total, color: 'rgba(255,255,255,0.9)', dot: null },
                        { label: t('sidebar.water'), value: stats.wasser, color: '#38bdf8', dot: '#38bdf8' },
                        { label: t('sidebar.gas'), value: stats.gas, color: '#f59e0b', dot: '#f59e0b' },
                        { label: t('common.highRisk'), value: stats.hoch, color: '#ef4444', dot: '#ef4444' },
                        { label: t('common.mediumRisk'), value: stats.mittel, color: '#f97316', dot: '#f97316' },
                        { label: t('common.lowRisk'), value: stats.niedrig, color: '#22c55e', dot: '#22c55e' },
                        { label: t('common.overdue'), value: stats.over, color: '#a78bfa', dot: '#a78bfa' },
                    ].map(s => (
                        <div key={s.label} className="estat">
                            {s.dot && <span className="estat-dot" style={{ background: s.dot }} />}
                            <span className="estat-value" style={{ color: s.color }}>{s.value}</span>
                            <span className="estat-label">{s.label}</span>
                        </div>
                    ))}
                </div>
                <div className="estats-legend">
                    {colorBy === 'risiko' && Object.entries(RISK_COLOR).map(([k, v]) => (
                        <span key={k} className="ldot-item">
                            <span className="ldot" style={{ background: v }} />
                            {k === 'Hoch' ? t('common.highRisk') : k === 'Mittel' ? t('common.mediumRisk') : t('common.lowRisk')}
                        </span>
                    ))}
                    {colorBy === 'sparte' && Object.entries(SPARTE_COLOR).map(([k, v]) => (
                        <span key={k} className="ldot-item">
                            <span className="ldot" style={{ background: v }} />
                            {k === 'Wasser' ? t('sidebar.water') : k}
                        </span>
                    ))}
                    {colorBy === 'lifespan' && (<>
                        <span className="ldot-item"><span className="ldot" style={{ background: '#f59e0b' }} />{t('common.overdue')}</span>
                        <span className="ldot-item"><span className="ldot" style={{ background: '#22c55e' }} />{t('mapExplorer.legend.inService')}</span>
                    </>)}
                    {colorBy === 'age' && [['< 40yr', '#22c55e'], ['40–60yr', '#f59e0b'], ['60–80yr', '#f97316'], ['> 80yr', '#ef4444']].map(([l, c]) => (
                        <span key={l} className="ldot-item"><span className="ldot" style={{ background: c }} />{l}</span>
                    ))}
                    {pipelineActive && (<>
                        <span className="estats-sep" />
                        {(fPipeline === 'gas' || fPipeline === 'alle') && (
                            <span className="ldot-item">
                                <span className="pipe-swatch" style={{ background: '#f59e0b' }} />{t('mapExplorer.legend.gasPipeline')}
                            </span>
                        )}
                        {(fPipeline === 'wasser' || fPipeline === 'alle') && (
                            <span className="ldot-item">
                                <span className="pipe-swatch" style={{ background: '#38bdf8' }} />{t('mapExplorer.legend.waterPipeline')}
                            </span>
                        )}
                    </>)}
                </div>
            </div>

            {/* ── Map body ───────────────────────────────────────────────── */}
            <div className="explorer-body">
                <div className={`explorer-map-wrap ${panelOpen ? 'panel-open' : ''}`}>
                    {loading && (
                        <div className="explorer-loading">
                            <div className="explorer-spinner" />
                            <span>{t('mapExplorer.loading')}</span>
                        </div>
                    )}
                    <MapContainer
                        center={[51.2811, 7.0354]}
                        zoom={14}
                        style={{ height: '100%', width: '100%' }}
                        zoomControl={false}
                    >
                        <TileLayer
                            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                            maxZoom={19}
                            keepBuffer={4}
                        />
                        <MapResizer />
                        <AutoFit records={filtered} />
                        <PipelineLayer allRecords={allRecords} show={fPipeline} />
                        <MarkerLayer filtered={filtered} colorBy={colorBy} onDotClick={handleDotClick} />
                    </MapContainer>
                </div>

                {/* ── Detail panel ─────────────────────────────────────── */}
                {panelOpen && selected && (
                    <aside className="explorer-detail">
                        <div className="ed-header">
                            <div className="ed-pills">
                                <span className="ed-pill" style={{
                                    background: (SPARTE_COLOR[selected.Sparte] ?? '#888') + '18',
                                    color: SPARTE_COLOR[selected.Sparte] ?? '#888',
                                    borderColor: (SPARTE_COLOR[selected.Sparte] ?? '#888') + '40',
                                }}>
                                    {selected.Sparte === 'Gas' ? <Flame size={11} /> : <Droplets size={11} />}
                                    {selected.Sparte === 'Wasser' ? t('sidebar.water') : selected.Sparte}
                                </span>
                                <span className="ed-pill" style={{
                                    background: (RISK_COLOR[selected.Risiko] ?? '#888') + '18',
                                    color: RISK_COLOR[selected.Risiko] ?? '#888',
                                    borderColor: (RISK_COLOR[selected.Risiko] ?? '#888') + '40',
                                }}>
                                    {selected.Risiko === 'Hoch' ? t('mapExplorer.riskLabels.high') : selected.Risiko === 'Mittel' ? t('mapExplorer.riskLabels.medium') : selected.Risiko === 'Niedrig' ? t('mapExplorer.riskLabels.low') : selected.Risiko}
                                </span>
                            </div>
                            <button className="ed-close" onClick={() => setPanelOpen(false)}><X size={14} /></button>
                        </div>
                        <div className="ed-name">{selected.Kundenname || 'Asset'}</div>
                        <div className="ed-addr">
                            {selected['Straße']} {selected.Hausnummer}
                            <span className="ed-city">, 42489 Wülfrath</span>
                        </div>
                        <div className="ed-rule" />
                        <div className="ed-grid">
                            {[
                                [t('mapExplorer.details.customerNo'), selected.Kundennummer],
                                [t('mapExplorer.details.utility'), selected.Sparte === 'Wasser' ? t('sidebar.water') : selected.Sparte],
                                [t('mapExplorer.details.installYear'), selected.Einbaujahr ?? '—'],
                                [t('mapExplorer.details.age'), selected.Alter ? `${selected.Alter} years` : '—'],
                                [t('mapExplorer.details.material'), selected.Werkstoff ?? '—'],
                                [t('mapExplorer.details.pressure'), selected.Druckstufe ?? '—'],
                                [t('mapExplorer.details.risk'), selected.Risiko === 'Hoch' ? t('mapExplorer.riskLabels.high') : selected.Risiko === 'Mittel' ? t('mapExplorer.riskLabels.medium') : selected.Risiko === 'Niedrig' ? t('mapExplorer.riskLabels.low') : selected.Risiko],
                                [t('mapExplorer.details.renewalBy'), selected['Erneuerung_empfohlen_bis'] ?? '—'],
                                [t('mapExplorer.details.overdue'), selected.over_lifespan ? t('mapExplorer.details.yes') : t('mapExplorer.details.no')],
                            ].map(([k, v]) => (
                                <div key={k} className="ed-row">
                                    <span className="ed-key">{k}</span>
                                    <span className="ed-val" style={{
                                        color: k === t('mapExplorer.details.risk') && v === t('mapExplorer.riskLabels.high') ? '#ef4444'
                                            : k === t('mapExplorer.details.overdue') && v === t('mapExplorer.details.yes') ? '#f59e0b'
                                                : undefined,
                                    }}>{String(v ?? '—')}</span>
                                </div>
                            ))}
                        </div>
                        <div className="ed-alerts">
                            {selected.over_lifespan && (
                                <div className="ed-alert ed-alert--warn">
                                    <Clock size={12} /> {t('mapExplorer.details.alertLifeExceeded')}
                                </div>
                            )}
                            {selected.Risiko === 'Hoch' && (
                                <div className="ed-alert ed-alert--danger">
                                    <AlertTriangle size={12} /> {t('mapExplorer.details.alertActionRequired')}
                                </div>
                            )}
                            {selected.Werkstoff === 'Asbestzement-(AZ)' && (
                                <div className="ed-alert ed-alert--danger">
                                    <Wrench size={12} /> {t('mapExplorer.details.alertAcPipe')}
                                </div>
                            )}
                        </div>
                    </aside>
                )}
            </div>
        </div>
    );
}
