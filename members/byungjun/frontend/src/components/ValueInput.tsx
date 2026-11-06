import { useState } from "react";

// "100% 이하" → 숫자 "100", 단위 "%", 방향 "이하". 숫자가 없으면(예: "흑자") null이라 직접 입력할 수 없다.
function parse(text: string) {
  const m = text.match(/^(-?[\d,]+(?:\.\d+)?)(\S*)(?: (.+))?$/);
  return m ? { number: m[1], unit: m[2], direction: m[3] ?? "" } : null;
}

type Props = {
  value: string; // 예: "100% 이하"
  onChange: (text: string, number: number) => void;
  showDirection?: boolean; // false면 "100%"처럼 방향 말을 숨긴다 (11 시뮬레이션)
};

// 수치를 누르면 숫자 입력칸으로 바뀐다. 단위·방향은 그대로 붙어 있고, Enter나 바깥을 누르면 반영된다.
export default function ValueInput({ value, onChange, showDirection = true }: Props) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const parsed = parse(value);
  if (!parsed) return <>{value}</>;

  const suffix = parsed.unit + (showDirection && parsed.direction ? ` ${parsed.direction}` : "");

  function commit() {
    setEditing(false);
    const n = Number(text.replace(/,/g, ""));
    if (text.trim() === "" || Number.isNaN(n)) return;
    const next = `${Math.abs(n) >= 100 ? n.toLocaleString("en-US") : n}${parsed!.unit}${parsed!.direction ? ` ${parsed!.direction}` : ""}`;
    if (next !== value) onChange(next, n);
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="value-box"
        aria-label="수치 직접 입력"
        onClick={() => { setText(parsed.number.replace(/,/g, "")); setEditing(true); }}
      >
        {parsed.number}{suffix}
      </button>
    );
  }
  return (
    <span className="value-box editing">
      <input
        autoFocus
        inputMode="decimal"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={(e) => e.target.select()}
        onBlur={commit}
        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
      />
      <span className="value-suffix">{suffix}</span>
    </span>
  );
}
