import { useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { askPrinciple, savePrinciple, updatePrinciple } from "../api";
import back from "../assets/icons/back.svg";
import BottomSheet from "../components/BottomSheet";
import Button from "../components/Button";
import ChatBubble from "../components/ChatBubble";
import ChatInput from "../components/ChatInput";
import Chip from "../components/Chip";
import IndicatorCard from "../components/IndicatorCard";
import Select from "../components/Select";
import { categoryLabel, findIndicator, groupByCategory } from "../data/indicators";
import { useApp } from "../store/AppContext";
import type { IndicatorSetting, Principle } from "../types";

// 대화로 원칙을 만들고(01·02-1·02) 고치는(08·02-2) 화면을 하나로 합친 것.
// 내 말, AI 답, 되묻기 선택지, 바뀐 값 요약이 위에서 아래로 쌓이고, 지표 카드는 맨 아래 하나만 있다가
// 새 답이 오면 한 줄로 접힌다. 대화는 이 화면에만 있고 새로고침·화면 이동·저장하면 사라진다.
type Msg =
  | { kind: "user"; text: string }
  | { kind: "ai"; text: string }
  | { kind: "options"; options: string[]; picked?: string }
  | { kind: "change"; name: string; before: string; after: string }
  | { kind: "result"; count: number }; // count: 그 시점에 대화로 정해진 지표 수 (접힌 이전 세팅에 보여준다)

const startSuggestions = [
  "빚 많은 회사는 피하고 싶어",
  "배당 꾸준한 곳이 좋아",
  "너무 비싼 주식은 싫어요",
  "적자 기업은 제외할래요",
  "성장하는 회사만 보고 싶어",
];
const editSuggestions = ["부채비율을 더 낮춰 줘", "배당 기준을 올려 줘", "성장성도 보고 싶어", "조건을 조금 느슨하게 해 줘"];

const lockedOf = (p?: Principle) => (p ? p.indicators.filter((i) => i.locked).map((i) => i.id) : []);
const rank = (i: IndicatorSetting, lockedIds: number[]) => (lockedIds.includes(i.id) ? 0 : i.source === "default" ? 2 : 1);
const hasDefaults = (p?: Principle) => (p ? p.indicators.some((i) => i.source === "default") : true);

// edit=false: 새 원칙 만들기("/"), edit=true: 저장된 원칙 고치기("/principles/edit")
export default function PrincipleChat({ edit = false }: { edit?: boolean }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { principles, setPrinciples, setCurrentId, editTargetId, setEditTargetId, setSimPrincipleId, setChanges } = useApp();
  const base = edit ? principles.find((p) => p.id === editTargetId) : undefined;

  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState<Principle | null>(null); // 대화로 만든(고친) 원칙. 고치기 화면에서는 대화 전까지 null
  const [lockedIds, setLockedIds] = useState<number[]>(() => lockedOf(base)); // 잠근 지표 id
  const [history, setHistory] = useState<string[]>([]); // 되묻기에 답하기 전까지 사용자가 한 말
  const [recentIds, setRecentIds] = useState<number[] | null>(null); // 방금 정해지거나 바뀐 지표 (null: 처음 만든 직후라 전체)
  const [pending, setPending] = useState<string | null>(null); // 서버가 바꾸는 동안 보여줄 입력 중 문구
  const [includeDefaults, setIncludeDefaults] = useState(() => hasDefaults(base)); // "그 외 지표(기본값)를 원칙에 포함"
  const [restOpen, setRestOpen] = useState(false); // 그 외 지표 펼치기
  const [sheetOpen, setSheetOpen] = useState(false); // 고치기: "내가 설정한 지표값 상세" 시트
  const endRef = useRef<HTMLDivElement>(null);
  const restRef = useRef<HTMLDivElement>(null);

  // 고칠 원칙을 바꾸면 대화를 처음부터 다시 시작한다
  useEffect(() => {
    setMessages([]);
    setDraft(null);
    setLockedIds(lockedOf(base));
    setHistory([]);
    setRecentIds(null);
    setPending(null);
    setIncludeDefaults(hasDefaults(base));
    setRestOpen(false);
    setSheetOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editTargetId]);

  // 새 메시지가 오면 맨 아래로, 그 외 지표를 펼치면 그 줄이 위로 오게
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages, pending]);
  useEffect(() => {
    if (restOpen) restRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [restOpen]);

  // 앱을 켰을 때 이미 원칙이 있으면 종목 검색으로 간다 (하단 [원칙 생성] 탭으로 온 경우는 새 원칙을 만든다)
  if (!edit && principles.length > 0 && !location.state?.fromNav) return <Navigate to="/stocks" replace />;

  const cur = draft ?? base; // 지금 보여주는 원칙

  async function send(text: string) {
    // 마지막 되묻기 선택지에 답한 것이면 고른 선택지를 표시한다
    setMessages((m) => {
      const last = m[m.length - 1];
      const marked = last?.kind === "options" && !last.picked ? [...m.slice(0, -1), { ...last, picked: text }] : m;
      return [...marked, { kind: "user", text }];
    });
    setPending(history.length > 0 ? "답을 반영하는 중이에요" : "말씀하신 대로 수치로 바꾸는 중이에요");
    const result = await askPrinciple(text, cur, lockedIds, history);
    setPending(null);

    if (result.needsClarify || !result.principle) {
      setHistory([...history, text]);
      const c = result.clarify;
      const labels = (c?.options ?? []).map((o) => o.label);
      setMessages((m) => [
        ...m,
        { kind: "ai", text: c?.message || "조금 더 구체적으로 말해 주세요." },
        ...(labels.length > 0 ? [{ kind: "options", options: labels } as Msg] : []),
      ]);
      return;
    }

    setHistory([]);
    // 모델 응답과 상관없이 잠긴 지표는 기존 수치를 그대로 유지한다
    const values = { ...result.principle.values };
    for (const id of lockedIds) if (cur?.values[id] !== undefined) values[id] = cur.values[id];
    const next: Principle = { ...result.principle, values, id: base?.id ?? "", name: base?.name ?? result.principle.name };

    // 이번 대화로 새로 정해졌거나 연산자·값이 바뀐 지표가 "방금 설정된 지표"
    const old = new Map((cur?.indicators ?? []).map((i) => [i.id, i]));
    setRecentIds(
      cur
        ? next.indicators
            .filter((i) => i.source !== "default")
            .filter((i) => {
              const o = old.get(i.id);
              return !o || o.source === "default" || o.operator !== i.operator || o.value !== i.value;
            })
            .map((i) => i.id)
        : null,
    );
    // 바뀐 값은 한 줄 요약으로 대화에 남긴다
    const changes: Msg[] = cur
      ? next.indicators
          .filter((i) => i.source !== "default" && cur.values[i.id] !== values[i.id])
          .slice(0, 4)
          .map((i) => ({ kind: "change", name: findIndicator(i.id).name, before: cur.values[i.id] ?? "없음", after: values[i.id] }))
      : [];
    setDraft(next);
    setMessages((m) => [
      ...m,
      { kind: "ai", text: next.bubble || "말씀하신 내용을 수치로 바꿨어요." },
      ...changes,
      { kind: "result", count: next.indicators.filter((i) => i.source !== "default").length },
    ]);
  }

  // 수치를 직접 입력하면 그 지표는 내가 정한 지표(user)가 된다
  function editValue(id: number, text: string, n: number) {
    const c = draft ?? base;
    if (!c) return;
    const next: Principle = {
      ...c,
      values: { ...c.values, [id]: text },
      indicators: c.indicators.map((i) => (i.id === id ? { ...i, value: n, source: "user" } : i)),
    };
    setDraft(next);
    setRecentIds([id]);
    setMessages((m) => [
      ...m,
      { kind: "change", name: findIndicator(id).name, before: c.values[id] ?? "없음", after: text },
      { kind: "result", count: next.indicators.filter((i) => i.source !== "default").length },
    ]);
  }

  function toggleLock(id: number) {
    setLockedIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }

  async function approve() {
    if (!draft) return;
    // "원칙에 포함"을 끄면 기본값 지표는 빼고, 대화로 정한 지표만 원칙으로 저장한다.
    const toSave = {
      ...draft,
      indicators: draft.indicators
        .filter((i) => includeDefaults || i.source !== "default")
        .map((i) => ({ ...i, locked: lockedIds.includes(i.id) })),
    };
    if (edit) {
      const before = principles.find((p) => p.id === draft.id)!;
      // 저장하는 지표 중 값이 달라진 것만. 이전 원칙에 없던 기본값 지표는 제외하고, 새로 정한 지표는 "없음"에서 바뀐 것으로 본다.
      const changes = toSave.indicators
        .filter((i) => before.values[i.id] !== draft.values[i.id] && (before.values[i.id] !== undefined || i.source !== "default"))
        .map((i) => ({ name: findIndicator(i.id).name, before: before.values[i.id] ?? "없음", after: draft.values[i.id] }));
      setChanges(changes);
      const updated = await updatePrinciple(toSave);
      setPrinciples(principles.map((p) => (p.id === updated.id ? updated : p)));
      navigate("/edit-done");
    } else {
      const saved = await savePrinciple(toSave);
      setPrinciples([...principles, saved]);
      setCurrentId(saved.id);
      if (principles.length === 0) {
        setEditTargetId(saved.id);
        setSimPrincipleId(saved.id);
      }
      navigate("/stocks");
    }
  }

  // ---- 지표 카드 (대화 맨 아래 하나) ----
  function card(d: Principle, id: number, mark?: "match" | "soft" | "changed" | "rest" | "off", prev?: string) {
    return (
      <IndicatorCard
        key={id}
        indicator={findIndicator(id)}
        value={d.values[id]}
        locked={lockedIds.includes(id)}
        onToggleLock={() => toggleLock(id)}
        onEditValue={(text, n) => editValue(id, text, n)}
        mark={mark}
        prev={prev}
        glow={!edit && mark === "match" && (recentIds === null || recentIds.includes(id))}
      />
    );
  }

  function resultCard(d: Principle) {
    const matchedIds = d.indicators.filter((i) => i.source !== "default").map((i) => i.id);
    const defaultIds = d.indicators.filter((i) => i.source === "default").map((i) => i.id);
    const saved = edit ? principles.find((p) => p.id === d.id) : undefined;
    // 고치기: 저장된 원칙과 달라진 지표(값이 바뀌었거나 기본값이던 지표를 새로 정한 경우)만 위에 보여준다
    const changedIds = saved
      ? matchedIds.filter((id) => {
          const old = saved.indicators.find((x) => x.id === id);
          return !old || old.source === "default" || saved.values[id] !== d.values[id];
        })
      : [];
    const shownIds = edit ? changedIds : matchedIds;
    const restIds = edit ? [...matchedIds.filter((id) => !changedIds.includes(id)), ...defaultIds] : defaultIds;
    const restMark = matchedIds.length > 0 ? (includeDefaults ? "rest" : "off") : undefined;
    return (
      <div className="chat-result">
        <h3 className="chat-result-title">{edit ? "이렇게 바뀌었어요!" : "이런 수치로 세팅했어요!"}</h3>
        <div className="zone match">
          <h3>{edit ? `바뀐 지표 · ${shownIds.length}개` : `해당 지표 · ${shownIds.length}개`}</h3>
          <p>{edit ? "나머지 지표는 그대로예요" : "말씀하신 내용에 맞춰 정한 지표예요"}</p>
        </div>
        {shownIds.map((id) => card(d, id, edit ? "changed" : "match", edit && saved && saved.values[id] !== d.values[id] ? saved.values[id] : undefined))}
        {restIds.length > 0 && (
          <div ref={restRef} className="zone rest rest-row" role="button" onClick={() => setRestOpen(!restOpen)}>
            <div>
              <h3>그 외 지표 · {restIds.length}개 {restOpen ? "⌃" : "›"}</h3>
              <p>{defaultIds.length === 0 ? "지금까지 정해 둔 지표예요" : includeDefaults ? "원칙에 함께 담을까요?" : "원칙에 담지 않아요. 판정서에도 안 나와요"}</p>
            </div>
            {defaultIds.length > 0 && (
              <label className="switch-box" onClick={(e) => e.stopPropagation()}>
                원칙에 포함
                <button
                  type="button"
                  role="switch"
                  aria-checked={includeDefaults}
                  className={`switch${includeDefaults ? " on" : ""}`}
                  onClick={() => setIncludeDefaults(!includeDefaults)}
                />
              </label>
            )}
          </div>
        )}
        {restOpen && (
          <>
            {edit && restIds.filter((id) => matchedIds.includes(id)).map((id) => card(d, id, "soft"))}
            {groupByCategory(restIds.filter((id) => defaultIds.includes(id))).map(([category, items]) => [
              <h3 key={category} className={`category${restMark === "off" ? " off" : ""}`}>{categoryLabel(category, items.length)}</h3>,
              ...items.map((i) => card(d, i.id, restMark)),
            ])}
          </>
        )}
      </div>
    );
  }

  const lastResult = messages.map((m) => m.kind).lastIndexOf("result");
  const lastOptions = messages.map((m) => m.kind).lastIndexOf("options");

  function thread() {
    return (
      <div className="scroll chat-thread">
        {messages.map((m, i) => {
          if (m.kind === "user") return <ChatBubble key={i} side="user">{m.text}</ChatBubble>;
          if (m.kind === "ai") return <ChatBubble key={i} side="ai">{m.text}</ChatBubble>;
          if (m.kind === "change") {
            return (
              <div key={i} className="chat-change">
                <b>{m.name}</b><span>{m.before}</span><i>→</i><em>{m.after}</em>
              </div>
            );
          }
          if (m.kind === "options") {
            const live = i === lastOptions && !m.picked && pending === null;
            return (
              <div key={i} className={`options${live ? "" : " done"}`}>
                {m.options.map((o) => (
                  <Chip key={o} selected={m.picked === o} onClick={() => live && send(o)}>{o}</Chip>
                ))}
              </div>
            );
          }
          if (i === lastResult && draft) return <div key={i}>{resultCard(draft)}</div>;
          return <div key={i} className="chat-collapsed">이전 세팅 · 해당 지표 {m.count}개 ›</div>;
        })}
        {pending !== null && (
          <ChatBubble side="ai"><span className="typing"><span className="dots"><i /><i /><i /></span>{pending}</span></ChatBubble>
        )}
        <div ref={endRef} />
      </div>
    );
  }

  const approveButton = draft && pending === null && messages[messages.length - 1]?.kind === "result" && (
    <Button onClick={approve}>{edit ? "이대로 수정할래요" : "이 원칙으로 시작해요"}</Button>
  );
  const talking = messages.length > 0 || pending !== null;

  // ---- 고치기 화면 위쪽 (뒤로 가기 + 원칙 고르기) ----
  const editHeader = (
    <>
      <div className="top-bar">
        <button className="back" onClick={() => navigate(-1)} aria-label="뒤로 가기">
          <img src={back} width={24} height={24} alt="" />
        </button>
        <h1 className="title s08-title">원칙 수정하기</h1>
      </div>
      {!talking && <h3 className="label">원칙을 선택하세요</h3>}
      <Select principles={principles} value={editTargetId} onChange={setEditTargetId} />
    </>
  );

  // ---- 처음(대화 전) ----
  if (!talking && !edit) {
    return (
      <div className="screen s01">
        <div className="logo">StockRuleKeeper</div>
        <div className="s01-center">
          <div className="guide">
            <h1 className="headline">{"어떤 원칙으로\n투자하고 싶으세요?"}</h1>
            <p className="s01-desc">평소 생각하는 대로 편하게 말해 주세요. 제가 숫자 기준으로 바꿔 드려요.</p>
          </div>
          <div className="s01-input">
            <ChatInput placeholder="지키고 싶은 투자 원칙을 말해 보세요" onSend={send} />
            <div className="chip-row">
              {startSuggestions.map((s) => (
                <Chip key={s} onClick={() => send(s)}>{s}</Chip>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!talking && edit) {
    const sorted = base ? [...base.indicators].sort((a, b) => rank(a, lockedIds) - rank(b, lockedIds) || a.id - b.id) : [];
    return (
      <div className="screen tall-gap">
        {editHeader}
        {base && (
          <button type="button" className="detail-btn" onClick={() => setSheetOpen(true)}>
            <span className="spark" />
            내가 설정한 지표값 상세보기
            <span aria-hidden>›</span>
          </button>
        )}
        <div className="guide s08-guide">
          <h2 className="headline-sm">어떻게 바꾸고 싶으세요?</h2>
          <p className="desc">말해 주시면 수치로 바꿔서 보여 드려요. 마음에 들면 그때 반영해요.</p>
        </div>
        <div className="spacer" />
        <div className="chip-row">
          {editSuggestions.map((s) => (
            <Chip key={s} onClick={() => send(s)}>{s}</Chip>
          ))}
        </div>
        <ChatInput placeholder="바꾸고 싶은 점을 말해 보세요" onSend={send} />
        {base && (
          <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)}>
            <div className="sheet-title">
              <h2>내가 설정한 지표값</h2>
            </div>
            <div className="rule-list">
              <div className="rule-list-head">
                <h3>이 원칙의 지표 · {sorted.length}개</h3>
                <span>잠근 지표 {lockedIds.length}개</span>
              </div>
              <p className="rule-list-note">수치를 눌러 직접 바꿔요 · 잠근 지표는 대화로 안 바뀌어요</p>
              <div className="rule-list-body open">
                {sorted.map((i) => (
                  <IndicatorCard
                    key={i.id}
                    indicator={findIndicator(i.id)}
                    value={base.values[i.id]}
                    locked={lockedIds.includes(i.id)}
                    onToggleLock={() => toggleLock(i.id)}
                    onEditValue={(text, n) => { editValue(i.id, text, n); setSheetOpen(false); }}
                    tag={i.source === "default" ? "default" : "user"}
                  />
                ))}
              </div>
            </div>
            <Button onClick={() => setSheetOpen(false)}>닫기</Button>
          </BottomSheet>
        )}
      </div>
    );
  }

  // ---- 대화 중 ----
  return (
    <div className="screen with-footer chat-screen">
      {edit ? editHeader : <div className="logo">StockRuleKeeper</div>}
      {thread()}
      {approveButton}
      <ChatInput
        placeholder={edit ? "바꾸고 싶은 점을 말해 보세요" : "직접 말해도 돼요"}
        busy={pending !== null}
        busyText={pending ?? ""}
        onSend={send}
      />
    </div>
  );
}
