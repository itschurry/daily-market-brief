import { PaperTradingTab } from '../components/PaperTradingTab';

export function PaperPortfolioPage() {
  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell">
          <PaperTradingTab />
        </div>
      </div>
    </div>
  );
}
