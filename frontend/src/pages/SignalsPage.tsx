import { RecommendationTab } from '../components/RecommendationTab';
import { useAnalysis } from '../hooks/useAnalysis';

export function SignalsPage() {
  const { refresh } = useAnalysis();
  return (
    <div className="app-shell">
      <div className="page-frame">
        <div className="content-shell">
          <RecommendationTab onRefresh={refresh} />
        </div>
      </div>
    </div>
  );
}
