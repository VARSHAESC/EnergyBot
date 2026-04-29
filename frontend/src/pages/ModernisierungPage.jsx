import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { useLanguage } from '../context/LanguageContext';
import { fmtNum } from '../utils/fmt';
import NetworkMap from '../tabs/NetworkMap';
import AiAssistant from '../tabs/AiAssistant';
import PageKpiGrid from '../components/ui/PageKpiGrid';
import { ShieldAlert } from 'lucide-react';
import './SubPage.css';

export default function ModernisierungPage() {
    const { kpis, detailedKpis, kpisLoading, activeUtility } = useApp();
    const { t } = useLanguage();
    const [activeTab, setActiveTab] = useState('chat');
    // const [mapFilter, setMapFilter] = useState(null); // reserved for future map restore
    const d = detailedKpis?.modernisierung;
    const p = 'pages.modernisierung';

    const tabs = [
        // { id: 'map', label: t('tabs.networkMap') }, // hidden — restore when ready
        { id: 'chat', label: t('tabs.aiAssistant') },
    ];

    const showWasser = activeUtility !== 'Gas';
    const showGas = activeUtility !== 'Wasser';
    const primaryValue = d?.critical_material ?? kpis?.modernization_issues;

    // const goToMap = (filter) => { setMapFilter(filter); setActiveTab('map'); }; // reserved

    const kpiItems = [
        {
            label: t(`${p}.kpis.critMat.label`),
            value: fmtNum(primaryValue),
            sub: t(`${p}.kpis.critMat.sub`),
            accent: '#ef4444', glow: 'danger',
        },
        showWasser && {
            label: t(`${p}.kpis.az.label`),
            value: fmtNum(d?.az_leitungen),
            sub: t(`${p}.kpis.az.sub`),
            accent: '#ef4444', glow: 'danger',
        },
        showGas && {
            label: t(`${p}.kpis.stahl.label`),
            value: fmtNum(d?.stahl_ohne_kks),
            sub: t(`${p}.kpis.stahl.sub`),
            accent: '#ef4444', glow: 'danger',
        },
        showWasser && {
            label: t(`${p}.kpis.schutzrohr.label`),
            value: fmtNum(d?.schutzrohr_nein),
            sub: t(`${p}.kpis.schutzrohr.sub`),
            accent: '#f59e0b',
        },
        {
            label: t(`${p}.kpis.noMsh.label`),
            value: fmtNum(d?.msh_nein),
            sub: t(`${p}.kpis.noMsh.sub`),
            accent: '#f59e0b',
        },
    ].filter(Boolean);

    const renderContent = () => {
        switch (activeTab) {
            // case 'map': return <NetworkMap filterConfig={mapFilter} />; // hidden — restore when ready
            case 'chat': return <AiAssistant />;
            default: return <AiAssistant />;
        }
    };

    return (
        <div className="subpage">
            <div className="page-header">
                <div className="page-header-top">
                    <div>
                        <div className="subpage-breadcrumb subpage-breadcrumb--warning">
                            <ShieldAlert size={13} /> {t(`${p}.breadcrumb`)}
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
