/**
 * Two-layer cache: memory (instant, per session) + localStorage (survives refresh).
 *
 * Memory TTL:      5 min  — fresh data, no stale reads within a session
 * localStorage TTL: 30 min — warm start on page reload within the same work session
 *
 * Usage:
 *   cacheGet('kpis_Gas')          → data | null
 *   cacheSet('kpis_Gas', payload) → void
 *   cacheInvalidate('kpis_Gas')   → void
 */

const MEM_TTL = 5  * 60 * 1000;   // 5 minutes
const LS_TTL  = 30 * 60 * 1000;   // 30 minutes
const LS_PFX  = 'swx_v1_';        // bump suffix if cache shape changes

const _mem = new Map();

export function cacheGet(key) {
    // 1. Memory hit (fastest)
    const m = _mem.get(key);
    if (m && Date.now() - m.ts < MEM_TTL) return m.data;

    // 2. localStorage hit (warm start after refresh)
    try {
        const raw = localStorage.getItem(LS_PFX + key);
        if (raw) {
            const { data, ts } = JSON.parse(raw);
            if (Date.now() - ts < LS_TTL) {
                _mem.set(key, { data, ts }); // promote to memory
                return data;
            }
            localStorage.removeItem(LS_PFX + key); // expired — clean up
        }
    } catch { /* storage unavailable or corrupted JSON */ }

    return null;
}

export function cacheSet(key, data) {
    const ts = Date.now();
    _mem.set(key, { data, ts });
    try {
        localStorage.setItem(LS_PFX + key, JSON.stringify({ data, ts }));
    } catch { /* quota exceeded or private mode */ }
}

export function cacheInvalidate(key) {
    _mem.delete(key);
    try { localStorage.removeItem(LS_PFX + key); } catch {}
}
