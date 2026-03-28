import { useEffect, useState } from 'react';
import { BacktestValidationPage } from './pages/BacktestValidationPage';
import { OverviewPage } from './pages/OverviewPage';
import { PaperPortfolioPage } from './pages/PaperPortfolioPage';
import { ReportsPage } from './pages/ReportsPage';
import { SignalsPage } from './pages/SignalsPage';

type RouteId = 'overview' | 'signals' | 'paper' | 'reports' | 'backtest';

const ROUTE_LABELS: Array<{ id: RouteId; label: string; path: string }> = [
  { id: 'overview', label: 'Overview', path: '/overview' },
  { id: 'signals', label: 'Signals', path: '/signals' },
  { id: 'paper', label: 'Paper Portfolio', path: '/paper' },
  { id: 'reports', label: 'Reports', path: '/reports' },
  { id: 'backtest', label: 'Backtest/Validation', path: '/backtest' },
];

function readRoute(): RouteId {
  const path = location.pathname.toLowerCase();
  if (path.startsWith('/signals')) return 'signals';
  if (path.startsWith('/paper')) return 'paper';
  if (path.startsWith('/reports')) return 'reports';
  if (path.startsWith('/backtest')) return 'backtest';
  return 'overview';
}

function navigateTo(route: RouteId) {
  const target = ROUTE_LABELS.find((item) => item.id === route);
  if (!target) return;
  history.pushState(null, '', target.path);
}

export default function App() {
  const [route, setRoute] = useState<RouteId>(readRoute);

  useEffect(() => {
    const handlePopState = () => {
      setRoute(readRoute());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  function move(routeId: RouteId) {
    navigateTo(routeId);
    setRoute(routeId);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return (
    <>
      <div className="tab-shell">
        <div className="tab-shell-row">
          <div className="tab-strip">
            {ROUTE_LABELS.map((item, index) => (
              <button
                key={item.id}
                onClick={() => move(item.id)}
                className={`tab-button ${route === item.id ? 'active' : ''}`}
              >
                <span className="tab-step">{String(index + 1).padStart(2, '0')}</span>
                <span className="tab-label">{item.label}</span>
                <span className="tab-help">Auto-Invest Console</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {route === 'overview' && <OverviewPage />}
      {route === 'signals' && <SignalsPage />}
      {route === 'paper' && <PaperPortfolioPage />}
      {route === 'reports' && <ReportsPage />}
      {route === 'backtest' && <BacktestValidationPage onBack={() => move('overview')} />}
    </>
  );
}
