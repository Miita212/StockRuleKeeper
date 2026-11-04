import lock from "../assets/icons/lock.svg";
import lockOpen from "../assets/icons/lock-open.svg";
import type { Indicator } from "../types";

type Props = {
  indicator: Indicator;
  value: string;
  compact?: boolean; // 07 시트: 설명·자물쇠 없이 한 줄
  locked?: boolean; // 02: 잠긴 지표는 대화로 수정해도 수치가 바뀌지 않는다
  onToggleLock?: () => void;
};

export default function IndicatorCard({ indicator, value, compact, locked, onToggleLock }: Props) {
  return (
    <div className={`indicator-card ${compact ? "compact" : ""}`}>
      <div className="code">{indicator.code}</div>
      <div className="indicator-text">
        <div className="indicator-name">{indicator.name}</div>
        {!compact && <div className="indicator-desc">{indicator.desc}</div>}
      </div>
      <div className="indicator-value">{value}</div>
      {!compact && (
        <button
          type="button"
          className={`lock-btn ${locked ? "locked" : ""}`}
          aria-pressed={!!locked}
          aria-label={`${indicator.name} 수치 ${locked ? "잠금 해제" : "잠그기"}`}
          onClick={onToggleLock}
        >
          <img src={locked ? lock : lockOpen} width={20} height={20} alt="" />
        </button>
      )}
    </div>
  );
}
