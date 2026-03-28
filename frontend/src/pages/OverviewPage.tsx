import { Header } from '../components/Header';
import { MarketTab } from '../components/MarketTab';
import { SummaryBar } from '../components/SummaryBar';
import { useAnalysis } from '../hooks/useAnalysis';

export function OverviewPage() {
  const { data: analysis, refresh: refreshAnalysis } = useAnalysis();
  const today = new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="app-shell">
      <div className="page-frame">
        <Header
          reportDate={today}
          generatedAt={analysis.generated_at}
          headline={analysis.summary_lines?.[0]}
        />
        <SummaryBar
          summaryLines={analysis.summary_lines || []}
          generatedAt={analysis.generated_at}
          onRefresh={refreshAnalysis}
        />
        <div className="content-shell">
          <MarketTab />
        </div>
      </div>
    </div>
  );
}
