import type { Indicator, Principle } from "../types";

// 핵심지표 20개 (project_details/06_UI_초안_정리.md). code·desc는 Figma 카드 문구, sample은 Figma 임시 기준값.
export const indicators: Indicator[] = [
  { id: 1, name: "부채비율", code: "부채", desc: "낮을수록 빚 부담이 적어요", category: "재무 건전성", sample: "100% 이하" },
  { id: 2, name: "차입금의존도", code: "차입", desc: "빌린 돈에 기대는 정도예요", category: "재무 건전성", sample: "30% 이하" },
  { id: 3, name: "EBITDA/금융비용", code: "이자", desc: "이자 낼 여력이에요", category: "재무 건전성", sample: "3배 이상" },
  { id: 4, name: "자본잠식률", code: "잠식", desc: "자본이 바닥났는지 봐요", category: "재무 건전성", sample: "0% 이하" },
  { id: 5, name: "영업이익", code: "영익", desc: "본업에서 번 돈이에요", category: "수익성", sample: "흑자" },
  { id: 6, name: "연속 영업흑자 연수", code: "흑자", desc: "몇 년째 흑자인지 봐요", category: "수익성", sample: "3년 이상" },
  { id: 7, name: "매출순이익률", code: "순익", desc: "매출 중 남는 이익이에요", category: "수익성", sample: "5% 이상" },
  { id: 8, name: "매출액 증가율", code: "매출", desc: "매출이 얼마나 늘었는지", category: "성장성", sample: "5% 이상" },
  { id: 9, name: "영업이익 증가율", code: "영증", desc: "본업 이익이 늘고 있는지", category: "성장성", sample: "5% 이상" },
  { id: 10, name: "주가수익비율", code: "PER", desc: "이익 대비 낮을수록 저렴해요", category: "가치", sample: "10 이하" },
  { id: 11, name: "주가순자산비율", code: "PBR", desc: "순자산 대비 낮을수록 저렴해요", category: "가치", sample: "1배 이하" },
  { id: 12, name: "12개월 배당수익률", code: "배당", desc: "주가 대비 받는 배당이에요", category: "배당", sample: "2% 이상" },
  { id: 13, name: "연속 배당 연수", code: "연배", desc: "몇 년째 배당을 주는지 봐요", category: "배당", sample: "3년 이상" },
  { id: 14, name: "시가총액", code: "시총", desc: "회사의 몸집 크기예요", category: "규모", sample: "1조원 이상" },
  { id: 15, name: "기간 수익률", code: "수익", desc: "정한 기간 동안 오른 정도", category: "주가·거래", sample: "5% 이상" },
  { id: 16, name: "52주 고점 대비", code: "고점", desc: "고점에서 얼마나 내려왔는지", category: "주가·거래", sample: "-20% 이내" },
  { id: 17, name: "52주 저점 대비", code: "저점", desc: "저점에서 얼마나 올랐는지", category: "주가·거래", sample: "50% 이내" },
  { id: 18, name: "60일 변동성", code: "변동", desc: "주가가 출렁이는 정도예요", category: "주가·거래", sample: "2% 이하" },
  { id: 19, name: "20일 평균 거래대금", code: "대금", desc: "하루 평균 거래된 금액이에요", category: "주가·거래", sample: "10억 이상" },
  { id: 20, name: "거래량 증가 배율", code: "거래", desc: "거래량이 갑자기 늘었는지", category: "주가·거래", sample: "2배 이상" },
];

export function findIndicator(id: number) {
  return indicators.find((i) => i.id === id)!;
}

// 지표 id들을 카테고리별로 묶는다 (화면에서 헤더 + 카드로 표시)
export function groupByCategory(ids: number[]) {
  const groups: [string, Indicator[]][] = [];
  for (const indicator of indicators) {
    if (!ids.includes(indicator.id)) continue;
    const last = groups[groups.length - 1];
    if (last && last[0] === indicator.category) last[1].push(indicator);
    else groups.push([indicator.category, [indicator]]);
  }
  return groups;
}

// 카테고리 헤더 문구 (예: "재무 건전성 · 4개")
export function categoryLabel(category: string, count: number) {
  return `${category} · ${count}개`;
}

// 원칙 한 줄 요약 (예: "원칙 20개 · 부채비율 100% 이하 외")
export function summarize(principle: Principle) {
  const ids = Object.keys(principle.values).map(Number);
  const first = indicators.find((i) => ids.includes(i.id));
  if (!first) return "원칙 0개";
  return `원칙 ${ids.length}개 · ${first.name} ${principle.values[first.id]}${ids.length > 1 ? " 외" : ""}`;
}
