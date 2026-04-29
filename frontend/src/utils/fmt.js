/** Format a numeric value as a plain integer string. No thousand separators, no decimals. */
export function fmtNum(v) {
    if (v == null || v === '—') return '—';
    const n = typeof v === 'number' ? v : Number(v);
    if (isNaN(n)) return '—';
    return String(Math.round(n));
}

/** Format a percentage as a plain integer with % sign. */
export function fmtPct(v) {
    if (v == null) return '—';
    return `${Math.round(Number(v))}%`;
}

/** Format an age value as "N Jahre" (Jahre / years). */
export function fmtAge(v, unit = 'Jahre') {
    if (v == null) return '—';
    return `${Math.round(Number(v))} ${unit}`;
}
