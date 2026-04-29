import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    PieChart, Pie, Cell
} from 'recharts';
import axios from 'axios';
import { API_BASE } from '../lib/api';
import { SkeletonChart, SkeletonTableRows } from '../components/ui/Skeleton';
import './Tabs.css';

/* Module-level cache — survives tab switches, cleared on page reload */
const _dataCache = {};

const StrategicAnalysis = React.memo(function StrategicAnalysis() {
    const { activeUtility } = useApp();

    const cached = _dataCache[activeUtility];
    const [summaries, setSummaries] = useState(cached?.summaries ?? {});
    const [loading, setLoading] = useState(!cached);

    useEffect(() => {
        if (_dataCache[activeUtility]) {
            setSummaries(_dataCache[activeUtility].summaries);
            setLoading(false);
            return;
        }
        let cancelled = false;
        setLoading(true);
        axios.get(`${API_BASE}/api/assets?utility=${activeUtility}`)
            .then(res => {
                if (cancelled) return;
                const data = {
                    summaries: res.data.summaries || {},
                };
                _dataCache[activeUtility] = data;
                setSummaries(data.summaries);
            })
            .catch(err => { if (!cancelled) console.error('Error fetching dynamic assets:', err); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [activeUtility]);

    if (loading) {
        return (
            <div className="tab-pane">
                <div className="chart-grid">
                    <SkeletonChart />
                    <SkeletonChart />
                </div>
            </div>
        );
    }

    const utilityKeys = Object.keys(summaries);

    return (
        <div className="tab-pane">
            <header className="tab-header">
                <h3>📊 Strategische Analyse: {activeUtility}</h3>
                <p>Übersicht der Infrastruktur-Verteilung.</p>
            </header>

            {utilityKeys.length === 0 ? (
                <div className="no-data-hint glass-card">
                    Keine Daten für diesen Bereich verfügbar.
                </div>
            ) : (
                utilityKeys.map(uKey => (
                    <div key={uKey} className="utility-analysis-block">
                        {utilityKeys.length > 1 && (
                            <h4 className="utility-block-title">📦 Sparte: {uKey}</h4>
                        )}
                        <div className="chart-grid">
                            <div className="chart-card glass-card">
                                <h4>Altersstruktur der Infrastruktur ({uKey})</h4>
                                <div className="chart-container">
                                    <ResponsiveContainer width="100%" height={300}>
                                        <BarChart data={summaries[uKey].age}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                            <XAxis dataKey="name" axisLine={false} tickLine={false} />
                                            <YAxis axisLine={false} tickLine={false} />
                                            <Tooltip cursor={{ fill: 'rgba(0,0,0,0.05)' }} />
                                            <Bar dataKey="value" name="Anzahl" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>

                            <div className="chart-card glass-card">
                                <h4>Risiko-Verteilung ({uKey})</h4>
                                <div className="chart-container">
                                    <ResponsiveContainer width="100%" height={300}>
                                        <PieChart>
                                            <Pie data={summaries[uKey].risk} cx="50%" cy="50%"
                                                innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value">
                                                {summaries[uKey].risk.map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip />
                                            <Legend />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    </div>
                ))
            )}
        </div>
    );
});

export default StrategicAnalysis;
