import { useState } from "react";
import { updatePrinciple } from "../api";
import { summarize } from "../data/indicators";
import { useApp } from "../store/AppContext";
import type { Principle } from "../types";
import S07_PrincipleDetailSheet from "./S07_PrincipleDetailSheet";

// 카드 탭: 07 시트 / "선택": 적용 중인 원칙으로 바꾸기 / "수정": 원칙 이름 바꾸기
export default function S06_PrincipleList() {
  const { principles, setPrinciples, currentId, setCurrentId } = useApp();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const current = principles.find((p) => p.id === currentId)!;
  const others = principles.filter((p) => p.id !== currentId);
  const selected = principles.find((p) => p.id === selectedId) ?? null;

  // 카드 안의 버튼·입력창은 카드 탭(시트 열기)과 따로 동작한다
  function startRename(e: React.MouseEvent, p: Principle) {
    e.stopPropagation();
    setName(p.name);
    setRenamingId(p.id);
  }

  async function saveName(e?: React.MouseEvent) {
    e?.stopPropagation();
    const trimmed = name.trim();
    const target = principles.find((p) => p.id === renamingId);
    setRenamingId(null);
    if (trimmed && target) {
      const renamed = await updatePrinciple({ ...target, name: trimmed });
      setPrinciples(principles.map((p) => (p.id === renamed.id ? renamed : p)));
    }
  }

  function choose(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    setCurrentId(id);
  }

  function open(id: string) {
    if (renamingId) return;
    setSelectedId(id);
  }

  function title(p: Principle, badge?: boolean) {
    if (p.id === renamingId) {
      return (
        <input
          className="name-input"
          autoFocus
          value={name}
          maxLength={20}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && saveName()}
        />
      );
    }
    return (
      <div className="principle-name">
        {p.name}
        {badge && <span className="badge">적용 중</span>}
      </div>
    );
  }

  function editButton(p: Principle) {
    return p.id === renamingId ? (
      <button className="btn-sm fill" onClick={saveName}>저장</button>
    ) : (
      <button className="btn-sm soft" onClick={(e) => startRename(e, p)}>수정</button>
    );
  }

  return (
    <div className="screen">
      <h1 className="title s06-title">원칙 리스트</h1>
      <h3 className="label">현재 적용 중인 원칙</h3>
      <div className="principle-card current" onClick={() => open(current.id)}>
        <div className="indicator-text">
          {title(current, true)}
          <div className="indicator-desc">{summarize(current)}</div>
        </div>
        {editButton(current)}
      </div>
      {others.length > 0 && <h3 className="label s06-label">내가 만든 다른 원칙</h3>}
      <div className="list">
        {others.map((p) => (
          <div key={p.id} className="principle-card" onClick={() => open(p.id)}>
            <div className="indicator-text">
              {title(p)}
              <div className="indicator-desc">{summarize(p)}</div>
            </div>
            {p.id !== renamingId && (
              <button className="btn-sm fill" onClick={(e) => choose(e, p.id)}>선택</button>
            )}
            {editButton(p)}
          </div>
        ))}
      </div>
      <S07_PrincipleDetailSheet principle={selected} onClose={() => setSelectedId(null)} />
    </div>
  );
}
