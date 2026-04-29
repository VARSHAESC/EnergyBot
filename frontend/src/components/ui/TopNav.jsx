import { NavLink } from 'react-router-dom';
import { Home, Map, Bot, Sun, Moon } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useTheme } from '../../context/ThemeContext';
import './TopNav.css';

export default function TopNav() {
    const { lang, toggleLang, t } = useLanguage();
    const { theme, toggleTheme } = useTheme();

    const navItems = [
        { path: '/dashboard/anschluesse',       labelKey: 'nav.connections' },
        { path: '/dashboard/kritisch',          labelKey: 'nav.critical' },
        { path: '/dashboard/ueber-nutzungsdauer', labelKey: 'nav.renewalDue' },
        { path: '/dashboard/modernisierung',    labelKey: 'nav.modernization' },
        { path: '/dashboard/map-explorer',      labelKey: 'nav.mapExplorer',    icon: Map },
        { path: '/dashboard/ai-intelligence',  labelKey: 'nav.aiIntelligence', icon: Bot },
    ];

    return (
        <header className="topnav">
            <NavLink
                to="/dashboard"
                end
                className={({ isActive }) => `topnav-brand ${isActive ? 'active' : ''}`}
            >
                <Home size={15} />
                <span>{t('nav.overview')}</span>
            </NavLink>

            <nav className="topnav-links">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `topnav-link ${isActive ? 'active' : ''} ${item.icon ? 'topnav-link--icon' : ''}`}
                    >
                        {item.icon && <item.icon size={13} />}
                        {t(item.labelKey)}
                    </NavLink>
                ))}
            </nav>

            <div className="topnav-controls">
                <button className="topnav-lang" onClick={toggleLang} title="Switch language">
                    {lang === 'de' ? 'EN' : 'DE'}
                </button>
                <button
                    className="topnav-theme"
                    onClick={toggleTheme}
                    title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                    aria-label="Toggle theme"
                >
                    {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
                </button>
            </div>
        </header>
    );
}
