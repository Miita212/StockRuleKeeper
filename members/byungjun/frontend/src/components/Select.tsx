import chevron from "../assets/icons/chevron-down.svg";
import type { Principle } from "../types";

type Props = {
  principles: Principle[];
  value: string;
  onChange: (id: string) => void;
  strong?: boolean; // 10: 파란 테두리, 높이 60
};

// 원칙 고르기 드롭다운 (08, 10)
export default function Select({ principles, value, onChange, strong }: Props) {
  return (
    <div className={`select ${strong ? "strong" : ""}`}>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {principles.map((p) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
      <img src={chevron} width={20} height={20} alt="" />
    </div>
  );
}
