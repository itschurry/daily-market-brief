import { BacktestPage } from '../components/BacktestPage';

export function BacktestValidationPage({ onBack }: { onBack: () => void }) {
  return <BacktestPage onBack={onBack} />;
}
