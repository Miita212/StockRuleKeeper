import { useRef, useState } from "react";
import { deletePrinciple, updatePrinciple } from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import Pager from "../components/Pager";
import ScrollText from "../components/ScrollText";
import { summarize } from "../data/indicators";
import usePageSwipe from "../hooks/usePageSwipe";
import { useApp } from "../store/AppContext";
import type { Principle } from "../types";
import S07_PrincipleDetailSheet from "./S07_PrincipleDetailSheet";

const PAGE_SIZE = 4; // 다른 원칙은 한 페이지에 4개까지
const LONG_PRESS_MS = 600; // 카드를 이만큼 누르고 있으면 삭제 안내가 뜬다

// 카드 탭: 07 시트 / 카드 꾹 누르기: 삭제 안내 / "선택": 적용 중인 원칙으로 바꾸기 / "수정": 원칙 이름 바꾸기
export default function S06_PrincipleList() {
  const { principles, setPrinciples, currentId, setCurrentId, editTargetId, setEditTargetId, simPrincipleId, setSimPrincipleId } = useApp();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null); // 삭제 확인 창에 떠 있는 원칙
  const [pageIndex, setPageIndex] = useState(0);
  const pressTimer = useRef<number>();
  const pressStart = useRef({ x: 0, y: 0 });
  const longPressed = useRef(false); // 꾹 누른 뒤 이어지는 클릭은 카드 탭으로 보지 않는다
  const current = principles.find((p) => p.id === currentId)!;
  const others = principles.filter((p) => p.id !== currentId);
  const pageCount = Math.max(1, Math.ceil(others.length / PAGE_SIZE));
  const page = Math.min(pageIndex, pageCount - 1); // 원칙을 지워 페이지가 줄면 마지막 페이지로
  const pageItems = others.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const swipe = usePageSwipe(
    () => setPageIndex(Math.min(page + 1, pageCount - 1)),
    () => setPageIndex(Math.max(page - 1, 0)),
  );
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

  // 카드를 누르고 있으면 삭제 안내가 뜬다. 손가락이 움직이면(스크롤·페이지 넘기기) 취소한다.
  function startPress(e: React.PointerEvent, id: string) {
    if (renamingId) return;
    longPressed.current = false;
    pressStart.current = { x: e.clientX, y: e.clientY };
    pressTimer.current = window.setTimeout(() => {
      longPressed.current = true;
      setDeleteId(id);
    }, LONG_PRESS_MS);
  }

  function movePress(e: React.PointerEvent) {
    if (Math.hypot(e.clientX - pressStart.current.x, e.clientY - pressStart.current.y) > 10) endPress();
  }

  function endPress() {
    window.clearTimeout(pressTimer.current);
  }

  async function remove() {
    const id = deleteId!;
    setDeleteId(null);
    await deletePrinciple(id);
    setPrinciples(principles.filter((p) => p.id !== id));
    // 지운 원칙을 가리키던 선택은 적용 중인 원칙으로 돌린다
    if (editTargetId === id) setEditTargetId(currentId);
    if (simPrincipleId === id) setSimPrincipleId(currentId);
  }

  function open(id: string) {
    if (longPressed.current) {
      longPressed.current = false;
      return;
    }
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
          maxLength={30}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && saveName()}
        />
      );
    }
    return (
      <div className="principle-name">
        <ScrollText text={p.name} />
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
    <div className="screen swipe-page" {...swipe}>
      <h1 className="title s06-title">원칙 리스트</h1>
      <h3 className="label">현재 적용 중인 원칙</h3>
      <div className="principle-card current" onClick={() => open(current.id)}>
        <div className="indicator-text">
          {title(current, true)}
          <div className="indicator-desc">{summarize(current)}</div>
        </div>
        {editButton(current)}
      </div>
      {others.length > 0 && (
        <div className="s06-label-row">
          <h3 className="label">내가 만든 다른 원칙</h3>
          {pageCount > 1 && <Pager page={page + 1} pageCount={pageCount} onChange={(n) => setPageIndex(n - 1)} />}
        </div>
      )}
      <div className="list">
        {pageItems.map((p) => (
          <div
            key={p.id}
            className="principle-card pressable"
            onClick={() => open(p.id)}
            onPointerDown={(e) => startPress(e, p.id)}
            onPointerMove={movePress}
            onPointerUp={endPress}
            onPointerLeave={endPress}
            onPointerCancel={endPress}
            onContextMenu={(e) => e.preventDefault()}
          >
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
      <ConfirmDialog
        open={deleteId !== null}
        title={`‘${principles.find((p) => p.id === deleteId)?.name ?? ""}’을 삭제할까요?`}
        description="삭제하면 이 원칙의 기록도 모두 사라지고, 되돌릴 수 없어요."
        confirmText="삭제"
        onConfirm={remove}
        onClose={() => setDeleteId(null)}
      />
      <S07_PrincipleDetailSheet principle={selected} onClose={() => setSelectedId(null)} />
    </div>
  );
}
