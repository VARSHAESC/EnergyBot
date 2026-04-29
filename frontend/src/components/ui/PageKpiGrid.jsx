import { SkeletonKpiCard } from './Skeleton';
import './PageKpiGrid.css';

/**
 * items:   { label, value, sub?, accent?, glow?, onClick? }
 * loading: show skeleton cards instead of real data
 * count:   number of skeleton cards to show (defaults to items.length or 4)
 */
export default function PageKpiGrid({ items = [], loading = false, count }) {
    const colCount = count ?? Math.min(items.length || 4, 4);

    if (loading || (!items.length && loading !== false)) {
        return (
            <div className="pkpi-grid" style={{ '--col-count': colCount }}>
                {Array.from({ length: colCount }, (_, i) => <SkeletonKpiCard key={i} />)}
            </div>
        );
    }

    if (!items.length) return null;

    return (
        <div className="pkpi-grid" style={{ '--col-count': Math.min(items.length, 4) }}>
            {items.map((item, i) => {
                const cls = [
                    'pkpi-card',
                    item.glow   ? `pkpi-glow-${item.glow}` : '',
                    item.onClick ? 'pkpi-clickable'          : '',
                ].filter(Boolean).join(' ');

                return (
                    <div
                        key={i}
                        className={cls}
                        onClick={item.onClick}
                        title={item.onClick ? 'Auf Karte anzeigen →' : undefined}
                    >
                        <div
                            className="pkpi-value"
                            style={item.accent ? { color: item.accent } : undefined}
                        >
                            {item.value ?? '—'}
                        </div>
                        <div className="pkpi-label">{item.label}</div>
                        {item.sub && <div className="pkpi-sub">{item.sub}</div>}
                        {item.onClick && (
                            <div className="pkpi-map-hint">Karte →</div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
