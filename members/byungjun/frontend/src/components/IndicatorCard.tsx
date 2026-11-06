import lock from "../assets/icons/lock.svg";
import lockOpen from "../assets/icons/lock-open.svg";
import type { Indicator } from "../types";

type Props = {
  indicator: Indicator;
  value: string;
  compact?: boolean; // 07 시트: 설명·자물쇠 없이 한 줄
  locked?: boolean; // 02: 잠긴 지표는 대화로 수정해도 수치가 바뀌지 않는다
  onToggleLock?: () => void;
  mark?: "match" | "soft" | "changed" | "rest" | "off"; // 02: match=대화로 정한 지표, soft=이전에 정한 지표, changed=방금 바꾼 지표, rest=기본값 지표, off=원칙에 포함하지 않는 기본값 지표
  prev?: string; // changed일 때 바꾸기 전 값
};

export default function IndicatorCard({ indicator, value, compact, locked, onToggleLock, mark, prev }: Props) {
  return (
    <div className={`indicator-card ${compact ? "compact" : ""}${mark ? ` mark-${mark}` : ""}`}>
      <div className="code">{indicator.code}</div>
      <div className="indicator-text">
        <div className="indicator-name">
          {indicator.name}
          {mark === "changed" && <span className="changed-pill">방금 바꿨어요</span>}
        </div>
        {!compact && <div className="indicator-desc">{indicator.desc}</div>}
      </div>
      <div className="indicator-value">
        {value}
        {prev && <span className="prev-value">이전 {prev}</span>}
      </div>
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
