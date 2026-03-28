import { AnalysisTab } from '../components/AnalysisTab';
import { useAnalysis } from '../hooks/useAnalysis';

export function ReportsPage() {
  const { data, status, refresh } = useAnalysis();

  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell">
          <AnalysisTab data={data} status={status} onRefresh={refresh} />
        </div>
      </div>
    </div>
  );
}
