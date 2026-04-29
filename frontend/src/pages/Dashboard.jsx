import { Outlet, useLocation } from 'react-router-dom';
import TopNav from '../components/ui/TopNav';
import Sidebar from '../components/ui/Sidebar';
import './Dashboard.css';

export default function Dashboard() {
    const { pathname } = useLocation();
    const fullBleed    = pathname.includes('map-explorer') || pathname.includes('ai-intelligence');

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <div className="dashboard-body">
                <TopNav />
                <main className={`dashboard-main${fullBleed ? ' dashboard-main--fullbleed' : ''}`}>
                    <Outlet />
                </main>
            </div>
        </div>
    );
}
