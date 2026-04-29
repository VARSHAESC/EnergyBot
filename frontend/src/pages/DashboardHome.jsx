import { Link } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useLanguage } from '../context/LanguageContext';
import { fmtNum } from '../utils/fmt';
import { ArrowRight, Zap, AlertTriangle, Clock, ShieldAlert } from 'lucide-react';
import { SkeletonHomeCard } from '../components/ui/Skeleton';
import './DashboardHome.css';

const kpiCards = [
    {
        path: '/dashboard/anschluesse',
        labelKey: 'nav.connections',
        descKey: 'pages.anschluesse.desc',
        icon: Zap,
        detailGroup: 'anschluesse',
        detailKey: 'total',
        kpiKey: 'total',
        accent: '#ffffff',
    },
    {
        path: '/dashboard/kritisch',
        labelKey: 'nav.critical',
        descKey: 'pages.kritisch.desc',
        icon: AlertTriangle,
        detailGroup: 'kritisch',
        detailKey: 'hoch_risiko',
        kpiKey: 'critical',
        accent: '#ef4444',
    },
    {
        path: '/dashboard/ueber-nutzungsdauer',
        labelKey: 'nav.renewalDue',
        descKey: 'pages.renewal.desc',
        icon: Clock,
        detailGroup: 'renewal',
        detailKey: 'over_lifespan',
        kpiKey: 'over_lifespan',
        accent: '#f59e0b',
    },
    {
        path: '/dashboard/modernisierung',
        labelKey: 'nav.modernization',
        descKey: 'pages.modernisierung.desc',
        icon: ShieldAlert,
        detailGroup: 'modernisierung',
        detailKey: 'critical_material',
        kpiKey: 'modernization_issues',
        accent: '#ffffff',
    },
];

export default function DashboardHome() {
    const { kpis, detailedKpis, kpisLoading, activeUtility } = useApp();
    const { t } = useLanguage();

    const isLoading = kpisLoading || kpis === null;

    return (
        <div className="home-page">

            {/* ── Hero ─────────────────────────────────────────────────────── */}
            <section className="home-hero">
                <div className="home-hero-label">{t('home.platformLabel')}</div>
                <h1 className="home-hero-title">STADTWERKE X</h1>
                <p className="home-hero-sub">{t('home.heroSub')}</p>
            </section>

            {/* ── About ────────────────────────────────────────────────────── */}
            <section className="home-about glass-card">
                <div className="home-about-grid">
                    <div className="home-about-col">
                        <h2>{t('home.whatIsIt')}</h2>
                        <p>{t('home.aboutText')}</p>
                    </div>
                    <div className="home-about-col">
                        <h2>{t('home.whatForIt')}</h2>
                        <ul className="home-feature-list">
                            {t('home.features').map((f, i) => <li key={i}>{f}</li>)}
                        </ul>
                    </div>
                </div>
                {activeUtility && activeUtility !== 'Alle Sparten' && activeUtility !== 'All Utilities' && (
                    <div className="home-utility-badge">
                        {t('home.activeUtility')}: <strong>{activeUtility}</strong>
                    </div>
                )}
            </section>

            {/* ── KPI Navigation Cards ─────────────────────────────────────── */}
            <section className="home-kpi-section">
                <h2 className="home-section-title">{t('home.sections')}</h2>

                {isLoading ? (
                    <div className="home-kpi-grid">
                        {kpiCards.map((_, i) => <SkeletonHomeCard key={i} />)}
                    </div>
                ) : (
                    <div className="home-kpi-grid">
                        {kpiCards.map((card) => {
                            const Icon  = card.icon;
                            const value = detailedKpis?.[card.detailGroup]?.[card.detailKey]
                                       ?? kpis?.[card.kpiKey];
                            return (
                                <Link key={card.path} to={card.path} className="home-kpi-card glass-card">
                                    <div className="home-kpi-card-top">
                                        <div className="home-kpi-icon"
                                            style={{ color: card.accent, borderColor: `${card.accent}22` }}>
                                            <Icon size={20} />
                                        </div>
                                        <span className="home-kpi-value" style={{ color: card.accent }}>
                                            {fmtNum(value)}
                                        </span>
                                    </div>
                                    <div className="home-kpi-label">{t(card.labelKey)}</div>
                                    <p className="home-kpi-desc">{t(card.descKey)}</p>
                                    <div className="home-kpi-cta">
                                        {t('home.openSection')} <ArrowRight size={14} />
                                    </div>
                                </Link>
                            );
                        })}
                    </div>
                )}
            </section>
        </div>
    );
}
