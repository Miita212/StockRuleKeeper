export type Indicator = {
  id: number;
  name: string;
  code: string; // 카드 왼쪽 동그라미 약칭 (예: "부채", "PER")
  desc: string; // 카드에 쓰는 한 줄 설명
  category: string;
  sample: string; // Figma 샘플 기준값 (임시)
};

// 서버가 저장하는 지표 한 개. 연산자·값은 서버 판정용, 화면에는 Principle.values 문구를 쓴다.
export type IndicatorSetting = {
  id: number;
  operator: string;
  value: number;
  unit: string;
  source: string;
  locked: boolean;
};

// values: 지표 id → 기준값 문자열 (예: { 1: "100% 이하" })
// id: 서버 원칙 번호의 문자열. 아직 저장 전인 초안은 "".
export type Principle = {
  id: string;
  name: string;
  values: Record<number, string>;
  indicators: IndicatorSetting[];
  reason?: string; // 07 시트 "이렇게 만들었어요" 설명
  bubble?: string; // 02 화면 말풍선 설명
};

export type Stock = {
  code: string;
  name: string;
  passCount: number;
  changeRate: number;
};

export type VerdictRow = {
  indicatorId: number;
  criterion: string;
  actual: string;
  pass: boolean;
};

export type Verdict = {
  stock: Stock;
  rows: VerdictRow[];
};

export type Change = {
  name: string;
  before: string;
  after: string;
};

// 되묻기: 선택지를 고르면 그 문구를 다음 말로 보낸다
export type Clarify = {
  message: string;
  options: { label: string }[];
};

// 13 종합 리포트 (project_details/07 스키마)
export type Report = {
  headline: string;
  what_changed: string;
  comparison: { label: string; before: string; after: string; note: string }[];
  stock_changes: string;
  cautions: string[];
  think_about: string[];
};

export type SimOutcome = {
  report: Report | null;
  reportSource: string; // "llm" | "template" 등 서버가 알려 주는 출처
  months: number;
  universeSize: number;
  period: { start: string; end: string };
};
