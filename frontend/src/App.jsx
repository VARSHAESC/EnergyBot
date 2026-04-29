import { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useApp } from './context/AppContext';

// Lazy load pages for better performance
const LandingPage = lazy(() => import('./pages/LandingPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const DashboardHome = lazy(() => import('./pages/DashboardHome'));
const AnschlussePage = lazy(() => import('./pages/AnschlussePage'));
const KritischPage = lazy(() => import('./pages/KritischPage'));
const UeberNutzungsdauerPage = lazy(() => import('./pages/UeberNutzungsdauerPage'));
const ModernisierungPage = lazy(() => import('./pages/ModernisierungPage'));
const MapExplorerPage     = lazy(() => import('./pages/MapExplorerPage'));
const AiIntelligencePage  = lazy(() => import('./pages/AiIntelligencePage'));

function App() {
  const { isAuthenticated } = useApp();

  return (
    <Suspense fallback={
      <div style={{
        background: '#050505',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        fontFamily: 'Outfit, sans-serif',
        letterSpacing: '2px',
        fontSize: '0.9rem'
      }}>
        STADTWERKE X — Initialisierung...
      </div>
    }>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/dashboard" /> : <LoginPage />}
        />
        <Route
          path="/dashboard"
          element={isAuthenticated ? <Dashboard /> : <Navigate to="/login" />}
        >
          <Route index element={<DashboardHome />} />
          <Route path="anschluesse" element={<AnschlussePage />} />
          <Route path="kritisch" element={<KritischPage />} />
          <Route path="ueber-nutzungsdauer" element={<UeberNutzungsdauerPage />} />
          <Route path="modernisierung" element={<ModernisierungPage />} />
          <Route path="map-explorer"    element={<MapExplorerPage />} />
          <Route path="ai-intelligence" element={<AiIntelligencePage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
