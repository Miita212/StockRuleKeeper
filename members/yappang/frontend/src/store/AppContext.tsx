import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { listPrinciples } from "../api";
import type { Change, Clarify, Principle, SimOutcome } from "../types";

// 화면들이 같이 쓰는 값
type AppState = {
  principles: Principle[];
  setPrinciples: (p: Principle[]) => void;
  currentId: string; // 적용 중인 원칙
  setCurrentId: (id: string) => void;
  userText: string; // 사용자가 처음 입력한 문장
  setUserText: (t: string) => void;
  draft: Principle | null; // 02 화면에서 승인 대기 중인 원칙
  setDraft: (p: Principle | null) => void;
  editTargetId: string; // 08에서 수정할 원칙
  setEditTargetId: (id: string) => void;
  changes: Change[]; // 14에 보여 줄 바뀐 내용
  setChanges: (c: Change[]) => void;
  simPrincipleId: string; // 시뮬레이션 대상 원칙
  setSimPrincipleId: (id: string) => void;
  simValues: Record<number, string>; // 11에서 수정한 기준값
  setSimValues: (v: Record<number, string>) => void;
  months: number; // 12에서 고른 기간
  setMonths: (m: number) => void;
  simResult: SimOutcome | null;
  setSimResult: (r: SimOutcome | null) => void;
  clarify: Clarify | null; // 02-1에서 보여 줄 되묻기
  setClarify: (c: Clarify | null) => void;
};

const AppContext = createContext<AppState>(null!);

export function AppProvider({ children }: { children: ReactNode }) {
  // 저장된 원칙은 서버에서 불러온다. 하나도 없으면 신규 사용자다.
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [principles, setPrinciples] = useState<Principle[]>([]);
  const [currentId, setCurrentId] = useState("");
  const [userText, setUserText] = useState("");
  const [draft, setDraft] = useState<Principle | null>(null);
  const [editTargetId, setEditTargetId] = useState("");
  const [changes, setChanges] = useState<Change[]>([]);
  const [simPrincipleId, setSimPrincipleId] = useState("");
  const [simValues, setSimValues] = useState<Record<number, string>>({});
  const [months, setMonths] = useState(3);
  const [simResult, setSimResult] = useState<SimOutcome | null>(null);
  const [clarify, setClarify] = useState<Clarify | null>(null);

  function load() {
    setError(false);
    listPrinciples()
      .then((list) => {
        setPrinciples(list);
        const firstId = list.length > 0 ? list[0].id : "";
        setCurrentId(firstId);
        setEditTargetId(firstId);
        setSimPrincipleId(firstId);
        setLoaded(true);
      })
      .catch(() => setError(true));
  }

  useEffect(load, []);

  if (error) {
    return (
      <div className="screen">
        <p>서버에 연결하지 못했어요. 서버가 켜져 있는지, 같은 Wi-Fi인지 확인해 주세요.</p>
        <button className="btn-sm fill" onClick={load}>다시 시도</button>
      </div>
    );
  }
  if (!loaded) return <div className="screen">불러오는 중...</div>;

  return (
    <AppContext.Provider
      value={{
        principles, setPrinciples,
        currentId, setCurrentId,
        userText, setUserText,
        draft, setDraft,
        editTargetId, setEditTargetId,
        changes, setChanges,
        simPrincipleId, setSimPrincipleId,
        simValues, setSimValues,
        months, setMonths,
        simResult, setSimResult,
        clarify, setClarify,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  return useContext(AppContext);
}
