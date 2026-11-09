import type { ReactNode } from "react";
import { ALIASES } from "./deactivate";
import { indicators } from "./indicators";

// 지표 이름과 자주 쓰는 다른 말. 긴 이름 먼저: "영업이익 증가율"이 "영업이익"에 먼저 잡히게.
const keys = indicators
  .flatMap((i) => [i.name, ...(ALIASES[i.id] ?? [])])
  .sort((a, b) => b.length - a.length);

const pattern = new RegExp(`(${keys.map((k) => k.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")).join("|")})`, "gi");

// 챗봇 답변에 나온 지표 이름을 굵게 만든다.
export function boldIndicators(text: string): ReactNode[] {
  return text.split(pattern).map((part, i) => (i % 2 === 1 ? <b key={i}>{part}</b> : part));
}
