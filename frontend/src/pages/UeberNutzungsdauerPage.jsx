import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { useLanguage } from '../context/LanguageContext';
import { fmtNum, fmtAge } from '../utils/fmt';
import NetworkMap from '../tabs/NetworkMap';
import StrategicAnalysis from '../tabs/StrategicAnalysis';
import AiAssistant from '../tabs/AiAssistant';
import PageKpiGrid from '../components/ui/PageKpiGrid';
import { Clock } from 'lucide-react';
import './SubPage.css';

export default function UeberNutzungsdauerPage() {
    const { kpis, detailedKpis, kpisLoading, activeUtility } = useApp();
    const { t } = useLanguage();
    const [activeTab, setActiveTab] = useState('analysis');
    // const [mapFilter, setMapFilter] = useState(null); // reserved for future map restore
    const d = detailedKpis?.ueber_nutzungsdauer;
    const p = 'pages.renewal';

    const tabs = [
        // { id: 'map', label: t('tabs.networkMap') }, // hidden — restore when ready
        { id: 'analysis', label: t('tabs.strategicAnalysis') },
        { id: 'chat', label: t('tabs.aiAssistant') },
    ];

    const showWasser = activeUtility !== 'Gas';
    const showGas = activeUtility !== 'Wasser';
    const primaryValue = d?.over_lifespan ?? kpis?.over_lifespan;

    // const goToMap = (filter) => { setMapFilter(filter); setActiveTab('map'); }; // reserved

    const kpiItems = [
        {
            label: t(`${p}.kpis.over.label`),
            value: fmtNum(primaryValue),
            sub: t(`${p}.kpis.over.sub`),
            accent: '#f59e0b', glow: 'warning',
        },
        {
            label: t(`${p}.kpis.next10.label`),
            value: fmtNum(d?.renewal_next_10yr),
            sub: t(`${p}.kpis.next10.sub`),
            accent: '#f59e0b', glow: 'warning',
        },
        {
            label: t(`${p}.kpis.next20.label`),
            value: fmtNum(d?.renewal_next_20yr),
            sub: t(`${p}.kpis.next20.sub`),
        },
        {
            label: t(`${p}.kpis.age80.label`),
            value: fmtNum(d?.age_gt_80),
            sub: t(`${p}.kpis.age80.allConnsNote`),
            accent: '#ef4444', glow: 'danger',
        },
        showWasser && {
            label: t(`${p}.kpis.age80w.label`),
            value: fmtNum(d?.age_gt_80_wasser),
            sub: t(`${p}.kpis.age80w.sub`),
            accent: '#ef4444',
        },
        showWasser && {
            label: t(`${p}.kpis.wOver.label`),
            value: fmtNum(d?.wasser_over),
            sub: t(`${p}.kpis.wOver.sub`),
        },
        showGas && {
            label: t(`${p}.kpis.gOver.label`),
            value: fmtNum(d?.gas_over),
            sub: t(`${p}.kpis.gOver.sub`),
        },
        {
            label: t(`${p}.kpis.oldest.label`),
            value: fmtAge(d?.oldest_asset_years),
            sub: t(`${p}.kpis.oldest.sub`),
            accent: '#ef4444',
        },
    ].filter(Boolean);

    const renderContent = () => {
        switch (activeTab) {
            // case 'map': return <NetworkMap filterConfig={mapFilter} />; // hidden — restore when ready
            case 'analysis': return <StrategicAnalysis />;
            case 'chat': return <AiAssistant />;
            default: return <StrategicAnalysis />;
        }
    };

    return (
        <div className="subpage">
            <div className="page-header">
                <div className="page-header-top">
                    <div>
                        <div className="subpage-breadcrumb subpage-breadcrumb--warning">
                            <Clock size={13} /> {t(`${p}.breadcrumb`)}
                        </div>
                        <h1>{t(`${p}.title`)}</h1>
                        <p>{t(`${p}.desc`)}</p>
                    </div>
                    <div className="page-kpi-badge">
                        <span className="kpi-value kpi-value--warning">{fmtNum(primaryValue)}</span>
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
