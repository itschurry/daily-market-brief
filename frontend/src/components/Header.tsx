interface Props {
  reportDate: string;
  generatedAt?: string;
  headline?: string;
}

export function Header({ reportDate, generatedAt, headline }: Props) {
  return (
    <div className="hero-banner">
      <div className="hero-topline">
        <span className="hero-brand">Daily Market Brief</span>
        <span className="hero-topline-copy">Read-first investment desk</span>
      </div>
      <div className="hero-grid">
        <div className="hero-copy-stack">
          <div className="hero-eyebrow">Morning Edition</div>
          <div className="hero-title">오늘 시장을 읽는 한 장의 브리프</div>
          <div className="hero-chip-row">
            <span className="hero-chip">리포트 날짜 {reportDate}</span>
            <span className="hero-chip">생성 {generatedAt || '확인 중'}</span>
            <span className="hero-chip">읽는 순서 오늘 리포트 → 액션 보드 → 관심종목</span>
          </div>
        </div>

        <div className="hero-sidecard">
          <div className="hero-sidecard-label">핵심 요약</div>
          <div className="hero-sidecard-copy">
            {headline || '오늘 시장의 핵심 요약을 불러오는 중입니다.'}
          </div>
        </div>
      </div>
    </div>
  );
}
