import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { askPrinciple, savePrinciple, updatePrinciple } from "../api";
import Button from "../components/Button";
import ChatBubble from "../components/ChatBubble";
import ChatInput from "../components/ChatInput";
import Chip from "../components/Chip";
import IndicatorCard from "../components/IndicatorCard";
import { categoryLabel, findIndicator, groupByCategory } from "../data/indicators";
import { useApp } from "../store/AppContext";
import type { Clarify } from "../types";

// edit=false: 02 (신규 원칙), edit=true: 02-2 (원칙 수정 흐름)
export default function S02_PrincipleSetup({ edit = false }: { edit?: boolean }) {
  const navigate = useNavigate();
  const {
    principles, setPrinciples, setCurrentId, setEditTargetId, setSimPrincipleId,
    draft, setDraft, setChanges,
  } = useApp();
  const [lockedIds, setLockedIds] = useState<number[]>( // 잠근 지표 id (저장된 원칙을 고칠 때는 기존 잠금에서 시작)
    draft ? draft.indicators.filter((i) => i.locked).map((i) => i.id) : [],
  );
  const [clarify, setClarify] = useState<Clarify | null>(null); // 수정 말이 모호해서 서버가 되물을 때의 질문과 선택지
  const [history, setHistory] = useState<string[]>([]); // 되묻기 전까지 사용자가 한 말
  const [modifying, setModifying] = useState(false); // 서버가 수치를 다시 바꾸는 중
  // "그 외 지표(기본값)를 원칙에 포함" 스위치. 저장된 원칙을 고치는 중이면 그 원칙이 기본값 지표를 담고 있었는지로 시작한다.
  const [includeDefaults, setIncludeDefaults] = useState(() => {
    const saved = edit && draft ? principles.find((p) => p.id === draft.id) : undefined;
    return saved ? saved.indicators.some((i) => i.source === "default") : true;
  });

  if (!draft) return <div className="screen">세팅할 원칙이 없어요.</div>;

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
        .map((i) => ({
          name: findIndicator(i.id).name,
          before: before.values[i.id] ?? "없음",
          after: draft.values[i.id],
        }));
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

  function toggleLock(id: number) {
    setLockedIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }

  // 되묻는 중이면 앞서 한 말을 history로 함께 보내, 선택지 답이 무엇에 대한 것인지 서버가 알게 한다.
  async function modify(text: string) {
    setModifying(true);
    const result = await askPrinciple(text, draft ?? undefined, lockedIds, history);
    setModifying(false);
    if (result.needsClarify || !result.principle) {
      setClarify(result.clarify);
      setHistory([...history, text]);
      return;
    }
    setClarify(null);
    setHistory([]);
    // 모델 응답과 상관없이 잠긴 지표는 기존 수치를 그대로 유지한다
    const values = { ...result.principle.values };
    for (const id of lockedIds) values[id] = draft!.values[id];
    setDraft({ ...result.principle, values, id: draft!.id, name: draft!.name });
  }

  // 대화로 정한 지표(user·inferred)는 맨 위에 따로 보여주고, 기본값 지표는 그 아래 카테고리별로 보여준다.
  const matchedIds = draft.indicators.filter((i) => i.source !== "default").map((i) => i.id);
  const restIds = draft.indicators.filter((i) => i.source === "default").map((i) => i.id);
  // 수정 흐름: 저장된 원칙과 달라진 지표(값이 바뀌었거나, 기본값이던 지표를 새로 정한 경우)가 "방금 바꾼 지표"
  const before = edit ? principles.find((p) => p.id === draft.id) : undefined;
  const changedIds = matchedIds.filter((id) => {
    if (!before) return false;
    const old = before.indicators.find((x) => x.id === id);
    return !old || old.source === "default" || before.values[id] !== draft.values[id];
  });
  const shownMatchedIds = [...changedIds, ...matchedIds.filter((id) => !changedIds.includes(id))];

  const restMark = matchedIds.length > 0 ? (includeDefaults ? "rest" : "off") : undefined;

  function card(id: number, mark?: "match" | "soft" | "changed" | "rest" | "off") {
    const prev = mark === "changed" && before && before.values[id] !== draft!.values[id] ? before.values[id] : undefined;
    return (
      <IndicatorCard
        key={id}
        indicator={findIndicator(id)}
        value={draft!.values[id]}
        locked={lockedIds.includes(id)}
        onToggleLock={() => toggleLock(id)}
        mark={mark}
        prev={prev}
      />
    );
  }

  return (
    <div className={`screen with-footer${modifying ? " s02-busy" : ""}`}>
      <h1 className="title">이런 수치로 세팅했어요!</h1>
      <div className={`scroll s02-scroll${modifying ? " busy" : ""}`}>
        <p className="s02-hint">아이콘을 누르면 자세한 설명이 나와요</p>
        <ChatBubble side="ai" size="sm">
          {modifying ? (
            <span className="typing"><span className="dots"><i /><i /><i /></span>말씀하신 대로 수치를 바꾸는 중이에요</span>
          ) : (
            clarify?.message || draft.bubble || "말씀하신 내용을 수치로 바꿨어요."
          )}
        </ChatBubble>
        {clarify && (
          <div className="options">
            {clarify.options.map((o) => (
              <Chip key={o.label} onClick={() => modify(o.label)}>{o.label}</Chip>
            ))}
          </div>
        )}
        {matchedIds.length > 0 && (
          <>
            <div className="zone match">
              <h3>해당 지표 · {matchedIds.length}개</h3>
              <p>{edit ? "지금까지 정해 둔 지표예요. 방금 바꾼 것은 맨 위에 표시돼요" : "말씀하신 내용에 맞춰 정한 지표예요"}</p>
            </div>
            {shownMatchedIds.map((id) => card(id, edit ? (changedIds.includes(id) ? "changed" : "soft") : "match"))}
          </>
        )}
        {matchedIds.length > 0 && restIds.length > 0 && (
          <div className="zone rest">
            <div>
              <h3>그 외 지표 · {restIds.length}개</h3>
              <p>{includeDefaults ? "원칙에 함께 담을까요?" : "원칙에 담지 않아요. 판정서에도 안 나와요"}</p>
            </div>
            <label className="switch-box">
              원칙에 포함
              <button
                type="button"
                role="switch"
                aria-checked={includeDefaults}
                className={`switch${includeDefaults ? " on" : ""}`}
                onClick={() => setIncludeDefaults(!includeDefaults)}
              />
            </label>
          </div>
        )}
        {groupByCategory(restIds).map(([category, items]) => [
          <h3 key={category} className={`category${restMark === "off" ? " off" : ""}`}>{categoryLabel(category, items.length)}</h3>,
          ...items.map((i) => card(i.id, restMark)),
        ])}
      </div>
      <Button onClick={approve}>{edit ? "이대로 수정할래요" : "이 원칙으로 시작해요"}</Button>
      <ChatInput placeholder="바꾸고 싶은 점을 말해 보세요" size="sm" busy={modifying} busyText="수치를 바꾸는 중이에요" onSend={modify} />
    </div>
  );
}
