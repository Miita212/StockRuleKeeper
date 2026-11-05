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

  if (!draft) return <div className="screen">세팅할 원칙이 없어요.</div>;

  async function approve() {
    if (!draft) return;
    const toSave = { ...draft, indicators: draft.indicators.map((i) => ({ ...i, locked: lockedIds.includes(i.id) })) };
    if (edit) {
      const before = principles.find((p) => p.id === draft.id)!;
      const changes = Object.keys(draft.values)
        .map(Number)
        .filter((id) => before.values[id] !== draft.values[id])
        .map((id) => ({
          name: findIndicator(id).name,
          before: before.values[id],
          after: draft.values[id],
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
    const result = await askPrinciple(text, draft ?? undefined, lockedIds, history);
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

  const groups = groupByCategory(Object.keys(draft.values).map(Number));

  return (
    <div className="screen with-footer">
      <h1 className="title">이런 수치로 세팅했어요!</h1>
      <div className="scroll s02-scroll">
        <p className="s02-hint">아이콘을 누르면 자세한 설명이 나와요</p>
        <ChatBubble side="ai" size="sm">{clarify?.message || draft.bubble || "말씀하신 내용을 수치로 바꿨어요."}</ChatBubble>
        {clarify && (
          <div className="options">
            {clarify.options.map((o) => (
              <Chip key={o.label} onClick={() => modify(o.label)}>{o.label}</Chip>
            ))}
          </div>
        )}
        {groups.map(([category, items]) => [
          <h3 key={category} className="category">{categoryLabel(category, items.length)}</h3>,
          ...items.map((i) => (
            <IndicatorCard
              key={i.id}
              indicator={i}
              value={draft.values[i.id]}
              locked={lockedIds.includes(i.id)}
              onToggleLock={() => toggleLock(i.id)}
            />
          )),
        ])}
      </div>
      <Button onClick={approve}>{edit ? "이대로 수정할래요" : "이 원칙으로 시작해요"}</Button>
      <ChatInput placeholder="바꾸고 싶은 점을 말해 보세요" size="sm" onSend={modify} />
    </div>
  );
}
