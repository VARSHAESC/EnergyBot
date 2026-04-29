import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { cacheGet, cacheSet } from '../lib/dataCache';
import { API_BASE } from '../lib/api';

const AppContext = createContext();
export const useApp = () => useContext(AppContext);

export const AppProvider = ({ children }) => {
    const [isAuthenticated, setIsAuthenticated] = useState(
        () => localStorage.getItem('sw_auth') === '1'
    );
    const [activeUtility, setActiveUtility] = useState('Alle Sparten');
    const [kpis,         setKpis]         = useState(null);
    const [detailedKpis, setDetailedKpis] = useState(null);
    const [kpisLoading,  setKpisLoading]  = useState(false);
    const [error,        setError]        = useState(null);
    const [selectedAsset, setSelectedAsset] = useState(null);
    const [activeTab,    setActiveTab]    = useState('analysis');

    const viewAssetOnMap = (asset) => {
        setSelectedAsset(asset);
        setActiveTab('map');
    };

    /* ─── Fetch (or background-refresh) KPI data ──────────────────────────────
       silent = true  → already showing cached data, update without loading flag
       silent = false → cold load, show kpisLoading = true until done
    ─────────────────────────────────────────────────────────────────────────── */
    const fetchKPIs = useCallback(async (utility, silent = false) => {
        if (!silent) setKpisLoading(true);
        try {
            const [summaryRes, detailedRes] = await Promise.all([
                axios.get(`${API_BASE}/api/kpis?utility=${utility}`),
                axios.get(`${API_BASE}/api/kpis/detailed?utility=${utility}`),
            ]);
            const payload = {
                kpis:         summaryRes.data,
                detailedKpis: detailedRes.data,
            };
            cacheSet(`kpis_${utility}`, payload);
            setKpis(payload.kpis);
            setDetailedKpis(payload.detailedKpis);
            setError(null);
        } catch (err) {
            console.error('Failed to fetch KPIs:', err);
            if (!silent) setError('Systemdaten konnten nicht geladen werden.');
        } finally {
            if (!silent) setKpisLoading(false);
        }
    }, []);

    /* ─── Stale-While-Revalidate on utility change ────────────────────────────
       1. Serve cached data instantly (no loading flicker)
       2. Silently refetch in background to keep data fresh
       3. If no cache → show loading, then fetch
    ─────────────────────────────────────────────────────────────────────────── */
    useEffect(() => {
        if (!isAuthenticated) return;

        const cached = cacheGet(`kpis_${activeUtility}`);
        if (cached) {
            setKpis(cached.kpis);
            setDetailedKpis(cached.detailedKpis);
            setKpisLoading(false);
            fetchKPIs(activeUtility, true); // background refresh
        } else {
            setKpis(null);
            setDetailedKpis(null);
            fetchKPIs(activeUtility, false); // cold load with spinner
        }
    }, [activeUtility, isAuthenticated, fetchKPIs]);

    const login = (username, password) => {
        if (username === 'admin' && password === 'esc_service_2026') {
            setIsAuthenticated(true);
            localStorage.setItem('sw_auth', '1');
            return true;
        }
        return false;
    };

    const logout = () => {
        setIsAuthenticated(false);
        localStorage.removeItem('sw_auth');
    };

    const value = {
        isAuthenticated,
        activeUtility,
        setActiveUtility,
        kpis,
        detailedKpis,
        loading:     kpisLoading, // keep legacy name so existing consumers don't break
        kpisLoading,
        error,
        login,
        logout,
        fetchKPIs:   () => fetchKPIs(activeUtility, false),
        activeTab,
        setActiveTab,
        selectedAsset,
        setSelectedAsset,
        viewAssetOnMap,
    };

    return (
        <AppContext.Provider value={value}>
            {children}
        </AppContext.Provider>
    );
};
