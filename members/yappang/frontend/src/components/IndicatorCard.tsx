import { useRef } from "react";
import lock from "../assets/icons/lock.svg";
import lockOpen from "../assets/icons/lock-open.svg";
import type { Indicator } from "../types";
import ValueInput from "./ValueInput";

type Props = {
  indicator: Indicator;
  value: string;
  compact?: boolean; // 07 시트: 설명·자물쇠 없이 한 줄
  locked?: boolean; // 02: 잠긴 지표는 대화로 수정해도 수치가 바뀌지 않는다
  onToggleLock?: () => void;
  mark?: "match" | "soft" | "changed" | "rest" | "off"; // 02: match=대화로 정한 지표, soft=이전에 정한 지표, changed=방금 바꾼 지표, rest=기본값 지표, off=원칙에 포함하지 않는 기본값 지표
  prev?: string; // changed일 때 바꾸기 전 값
  onEditValue?: (text: string, number: number) => void; // 있으면 수치를 눌러 직접 입력할 수 있다
  glow?: boolean; // 02: 방금 대화로 정해지거나 바뀐 지표는 파란 테두리에 은은한 빛이 난다
  pill?: string; // changed일 때 이름 옆 표시 (기본 "방금 바꿨어요", 비활성화한 지표는 "비활성화됨")
  onLongPress?: () => void; // 있으면 카드를 꾹 눌러 비활성화 안내를 띄울 수 있다
  tag?: "user" | "default"; // 08: 설명 줄 대신 "내가 정한 지표"/"기본값"을 보여준다
};

export default function IndicatorCard({ indicator, value, compact, locked, onToggleLock, mark, prev, tag, glow, onEditValue, onLongPress, pill }: Props) {
  const timer = useRef<number>();
  const start = useRef({ x: 0, y: 0 });
  const longPressed = useRef(false); // 꾹 누른 뒤 이어지는 클릭(수치 입력 등)은 막는다
  const stop = () => window.clearTimeout(timer.current);
  const press = onLongPress
    ? {
        onPointerDown: (e: React.PointerEvent) => {
          if ((e.target as HTMLElement).closest("input")) return;
          longPressed.current = false;
          start.current = { x: e.clientX, y: e.clientY };
          timer.current = window.setTimeout(() => {
            longPressed.current = true;
            onLongPress();
          }, 600);
        },
        onPointerMove: (e: React.PointerEvent) => {
          if (Math.hypot(e.clientX - start.current.x, e.clientY - start.current.y) > 10) stop();
        },
        onPointerUp: stop,
        onPointerLeave: stop,
        onPointerCancel: stop,
        onContextMenu: (e: React.MouseEvent) => e.preventDefault(),
        onClickCapture: (e: React.MouseEvent) => {
          if (longPressed.current) {
            e.stopPropagation();
            e.preventDefault();
            longPressed.current = false;
          }
        },
      }
    : {};
  return (
    <div {...press} className={`indicator-card ${compact ? "compact" : ""}${mark ? ` mark-${mark}` : ""}${tag ? ` tag-${tag}` : ""}${glow ? " glow" : ""}${onLongPress ? " pressable" : ""}`}>
      <div className="code">{indicator.code}</div>
      <div className="indicator-text">
        <div className="indicator-name">
          {indicator.name}
          {mark === "changed" && <span className="changed-pill">{pill ?? "방금 바꿨어요"}</span>}
        </div>
        {!compact && (tag
          ? <div className={`indicator-tag ${tag}`}>{tag === "user" ? "내가 정한 지표" : "기본값"}</div>
          : <div className="indicator-desc">{indicator.desc}</div>)}
      </div>
      <div className="indicator-value">
        {onEditValue && !compact ? <ValueInput value={value} onChange={onEditValue} /> : value}
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
