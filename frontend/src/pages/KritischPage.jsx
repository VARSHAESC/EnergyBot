import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { useLanguage } from '../context/LanguageContext';
import { fmtNum, fmtPct } from '../utils/fmt';
import NetworkMap from '../tabs/NetworkMap';
import StrategicAnalysis from '../tabs/StrategicAnalysis';
import AiAssistant from '../tabs/AiAssistant';
import PageKpiGrid from '../components/ui/PageKpiGrid';
import { AlertTriangle } from 'lucide-react';
import './SubPage.css';

export default function KritischPage() {
    const { kpis, detailedKpis, kpisLoading, activeUtility } = useApp();
    const { t } = useLanguage();
    const [activeTab, setActiveTab] = useState('analysis');
    // const [mapFilter, setMapFilter] = useState(null); // reserved for future map restore
    const d = detailedKpis?.kritisch;
    const p = 'pages.kritisch';

    const tabs = [
        // { id: 'map', label: t('tabs.networkMap') }, // hidden — restore when ready
        { id: 'analysis', label: t('tabs.strategicAnalysis') },
        { id: 'chat',     label: t('tabs.aiAssistant') },
    ];

    const showWasser = activeUtility !== 'Gas';
    const showGas    = activeUtility !== 'Wasser';
    const primaryValue = d?.hoch_risiko ?? kpis?.critical;

    // const goToMap = (filter) => { setMapFilter(filter); setActiveTab('map'); }; // reserved

    const kpiItems = [
        {
            label: t(`${p}.kpis.hoch.label`),
            value: fmtNum(primaryValue),
            sub: `${fmtPct(d?.high_risk_pct)} ${t(`${p}.kpis.hoch.sub`)}`,
            accent: '#ef4444', glow: 'danger',
        },
        {
            label: t(`${p}.kpis.overdue.label`),
            value: fmtNum(d?.inspection_overdue),
            sub: t(`${p}.kpis.overdue.sub`),
            accent: '#ef4444', glow: 'danger',
        },
        showWasser && {
            label: t(`${p}.kpis.overdueWasser.label`),
            value: fmtNum(d?.overdue_wasser),
            sub: t(`${p}.kpis.overdueWasser.sub`),
            accent: '#ef4444',
        },
        showGas && {
            label: t(`${p}.kpis.overdueGas.label`),
            value: fmtNum(d?.overdue_gas),
            sub: t(`${p}.kpis.overdueGas.sub`),
            accent: '#ef4444',
        },
        showWasser && {
            label: t(`${p}.kpis.wKritisch.label`),
            value: fmtNum(d?.wasser_kritisch),
            sub: t(`${p}.kpis.wKritisch.sub`),
            glow: 'danger',
        },
        showGas && {
            label: t(`${p}.kpis.gKritisch.label`),
            value: fmtNum(d?.gas_kritisch),
            sub: t(`${p}.kpis.gKritisch.sub`),
            glow: 'danger',
        },
    ].filter(Boolean);

    const renderContent = () => {
        switch (activeTab) {
            // case 'map': return <NetworkMap filterConfig={mapFilter} />; // hidden — restore when ready
            case 'analysis': return <StrategicAnalysis />;
            case 'chat':     return <AiAssistant />;
            default:         return <StrategicAnalysis />;
        }
    };

    return (
        <div className="subpage">
            <div className="page-header">
                <div className="page-header-top">
                    <div>
                        <div className="subpage-breadcrumb subpage-breadcrumb--danger">
                            <AlertTriangle size={13} /> {t(`${p}.breadcrumb`)}
                        </div>
                        <h1>{t(`${p}.title`)}</h1>
                        <p>{t(`${p}.desc`)}</p>
                    </div>
                    <div className="page-kpi-badge">
                        <span className="kpi-value kpi-value--danger">{fmtNum(primaryValue)}</span>
                        <span className="kpi-sublabel">{t(`${p}.badgeLabel`)}</span>
                    </div>
                </div>
            </div>

            <PageKpiGrid items={kpiItems} loading={kpisLoading} count={4} />

            <div className="tab-container glass-card">
                <div className="tab-navigation">
                    {tabs.map(tab => (
                        <button key={tab.id} className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>
                            {tab.label}
                        </button>
                    ))}
                </div>
                <div className="tab-content">{renderContent()}</div>
            </div>
        </div>
    );
}
