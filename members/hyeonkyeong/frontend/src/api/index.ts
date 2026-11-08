// 서버(FastAPI) 호출 경계. 화면은 이 파일의 함수만 부른다.
// 서버 주소는 VITE_API_BASE (frontend/.env). 폰에서는 노트북의 같은 Wi-Fi 주소로 바꾼다.
import type { Clarify, IndicatorSetting, Principle, SimOutcome, Stock, Verdict } from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`서버 오류 ${res.status}`);
  return res.json();
}

// 서버 원칙 → 화면용 Principle (values 키를 숫자 id로)
type ServerPrinciple = {
  id?: number;
  name: string;
  reason?: string;
  explain_card?: string;
  explain_bubble?: string;
  values: Record<string, string>;
  indicators: IndicatorSetting[];
};

function toPrinciple(p: ServerPrinciple): Principle {
  const values: Record<number, string> = {};
  for (const [id, text] of Object.entries(p.values)) values[Number(id)] = text;
  return {
    id: p.id === undefined ? "" : String(p.id),
    name: p.name,
    values,
    indicators: p.indicators,
    reason: p.reason || p.explain_card || undefined,
    bubble: p.explain_bubble || undefined,
  };
}

// 서버가 저장하는 값만 보낸다 (화면용 문구 제외)
function settings(p: Principle) {
  return p.indicators.map(({ id, operator, value, unit, source, locked }) => ({
    id, operator, value, unit, source, locked,
  }));
}

export async function listPrinciples(): Promise<Principle[]> {
  return (await call<ServerPrinciple[]>("/principles")).map(toPrinciple);
}

// 새 원칙 저장 (02 "이 원칙으로 시작해요")
export async function savePrinciple(p: Principle): Promise<Principle> {
  const saved = await call<ServerPrinciple>("/principles", "POST", {
    name: p.name, indicators: settings(p), reason: p.reason ?? "",
  });
  return toPrinciple(saved);
}

// 기존 원칙 수정 (서버에 새 버전으로 쌓인다)
export async function updatePrinciple(p: Principle): Promise<Principle> {
  const saved = await call<ServerPrinciple>(`/principles/${p.id}`, "PUT", {
    name: p.name, indicators: settings(p), reason: p.reason ?? "",
  });
  return toPrinciple(saved);
}

// 원칙 삭제 (서버에서 그 원칙의 모든 버전이 지워진다)
export async function deletePrinciple(id: string): Promise<void> {
  await call(`/principles/${id}`, "DELETE");
}

// FR-01: 자연어 → 원칙(지표 기준값). 되묻기가 필요하면 clarify에 질문과 선택지가 온다.
// base가 있으면 기존 원칙(또는 초안)을 수정하는 흐름이다.
// lockedIds: 사용자가 잠근 지표. 서버가 이 지표의 수치를 바꾸지 않는다.
export async function askPrinciple(
  text: string,
  base?: Principle,
  lockedIds: number[] = [],
  history: string[] = [],
): Promise<{ needsClarify: boolean; clarify: Clarify | null; principle: Principle | null }> {
  const r = await call<ServerPrinciple & { needs_clarification: boolean; clarify: Clarify | null }>(
    "/principles/ask",
    "POST",
    { text, base_indicators: base ? settings(base) : null, locked_ids: lockedIds, history },
  );
  if (r.needs_clarification) return { needsClarify: true, clarify: r.clarify, principle: null };
  return { needsClarify: false, clarify: null, principle: toPrinciple(r) };
}

// 03: 원칙 충족 개수 순 종목 목록. q 없음 = 전체(DB 값, 즉시), q 있음 = 검색한 종목(한투 최신 값)
export async function searchStocks(principle: Principle, q = ""): Promise<Stock[]> {
  return call<Stock[]>(`/stocks?principle_id=${principle.id}&q=${encodeURIComponent(q)}`);
}

// 03 검색창 아래: 내 원칙(사용자가 정한 지표)을 모두 충족하는 추천 종목
export async function recommendStocks(principle: Principle): Promise<Stock[]> {
  return call<Stock[]>(`/stocks/recommend?principle_id=${principle.id}`);
}

// 04: 코드가 수행하는 판정 (지표별 충족 여부)
export async function getVerdict(code: string, principle: Principle): Promise<Verdict> {
  return call<Verdict>(`/stocks/${code}/verdict?principle_id=${principle.id}`);
}

// "100% 이하" 같은 문구에서 숫자만 꺼낸다 ("흑자"처럼 숫자가 없으면 null)
function numberOf(text: string): number | null {
  const m = text.replace(/,/g, "").match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : null;
}

// FR-03: 시뮬레이션. 수정 전 원칙(principle)과 11에서 고친 값(values)을 서버에 보내고 리포트를 받는다.
export async function runSimulation(
  principle: Principle,
  values: Record<number, string>,
  months: number,
  lockedIds: number[] = [],
): Promise<SimOutcome> {
  const changes = principle.indicators
    .filter((i) => values[i.id] !== principle.values[i.id] && numberOf(values[i.id]) !== null)
    .map((i) => ({ id: i.id, operator: i.operator, value: numberOf(values[i.id])! }));
  const r = await call<{
    report: SimOutcome["report"];
    report_source: string;
    result: { universe: { size: number }; period: SimOutcome["period"] };
  }>("/simulation", "POST", {
    principle_id: Number(principle.id), changes, months, locked_ids: lockedIds, with_report: true,
  });
  return {
    report: r.report,
    reportSource: r.report_source,
    months,
    universeSize: r.result.universe.size,
    period: r.result.period,
  };
}

// 가상 주식앱에서 "공유하기"를 눌렀는지 확인 (몇 초마다 부른다)
export async function latestShare(afterId: number): Promise<{ id: number; code: string; name: string } | null> {
  return call(`/shares/latest?after_id=${afterId}`);
}
