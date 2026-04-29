import './Skeleton.css';

/* ─── Primitive ──────────────────────────────────────────────────────────────── */
export function Bone({ w, h = '1em', r = 6, style }) {
    return (
        <span
            className="skel-bone"
            style={{ width: w, height: h, borderRadius: r, ...style }}
            aria-hidden="true"
        />
    );
}

/* ─── PageKpiGrid card (pkpi-card layout) ────────────────────────────────────── */
export function SkeletonKpiCard() {
    return (
        <div className="pkpi-card skel-card" aria-hidden="true">
            <Bone w="45%" h="2rem"  r={4} />
            <Bone w="65%" h="0.65rem" r={3} style={{ marginTop: 10 }} />
            <Bone w="80%" h="0.65rem" r={3} style={{ marginTop: 4 }} />
        </div>
    );
}

/* ─── DashboardHome KPI card (home-kpi-card layout) ─────────────────────────── */
export function SkeletonHomeCard() {
    return (
        <div className="home-kpi-card glass-card skel-home-card skel-card" aria-hidden="true">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Bone w={40} h={40} r={10} />
                <Bone w="38%" h="2.2rem" r={4} />
            </div>
            <Bone w="52%" h="0.72rem" r={3} />
            <Bone w="90%" h="0.85rem" r={3} />
            <Bone w="72%" h="0.85rem" r={3} />
            <Bone w="42%" h="0.75rem" r={3} style={{ marginTop: 4 }} />
        </div>
    );
}

/* ─── StrategicAnalysis chart placeholder ────────────────────────────────────── */
export function SkeletonChart() {
    return (
        <div className="chart-card glass-card skel-chart-card skel-card" aria-hidden="true">
            <Bone w="55%" h="0.9rem" r={3} />
            <Bone w="100%" h={260} r={8} />
        </div>
    );
}

/* ─── StrategicAnalysis table rows ───────────────────────────────────────────── */
export function SkeletonTableRows({ count = 8 }) {
    return Array.from({ length: count }, (_, i) => (
        <tr key={i} className="skel-tr" aria-hidden="true">
            <td><Bone w="75%" h="0.82rem" r={3} /></td>
            <td><Bone w="55%" h="0.82rem" r={3} /></td>
            <td><Bone w={46}  h="1.35rem" r={10} /></td>
            <td><Bone w="70%" h="0.82rem" r={3} /></td>
            <td><Bone w={46}  h="1.35rem" r={10} /></td>
            <td><Bone w="38%" h="0.82rem" r={3} /></td>
            <td><Bone w={26}  h={26}      r={6} /></td>
        </tr>
    ));
}

/* ─── MapExplorer filter-bar skeleton chips ──────────────────────────────────── */
export function SkeletonFilterChips({ count = 5 }) {
    const widths = [96, 80, 110, 72, 88];
    return (
        <div className="skel-map-bar" aria-hidden="true">
            {Array.from({ length: count }, (_, i) => (
                <Bone key={i} w={widths[i % widths.length]} h={28} r={6} />
            ))}
        </div>
    );
}
