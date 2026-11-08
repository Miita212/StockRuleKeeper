import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { askPrinciple } from "../api";
import back from "../assets/icons/back.svg";
import Button from "../components/Button";
import BottomSheet from "../components/BottomSheet";
import ChatInput from "../components/ChatInput";
import ChatBubble from "../components/ChatBubble";
import Chip from "../components/Chip";
import IndicatorCard from "../components/IndicatorCard";
import Select from "../components/Select";
import { findIndicator } from "../data/indicators";
import { useApp } from "../store/AppContext";
import type { Clarify, IndicatorSetting, Principle } from "../types";

const suggestions = ["부채비율을 더 낮춰 줘", "배당 기준을 올려 줘", "성장성도 보고 싶어", "조건을 조금 느슨하게 해 줘"];

const lockedOf = (p?: Principle) => (p ? p.indicators.filter((i) => i.locked).map((i) => i.id) : []);
const rank = (i: IndicatorSetting, lockedIds: number[]) => (lockedIds.includes(i.id) ? 0 : i.source === "default" ? 2 : 1);

export default function S08_PrincipleEdit() {
  const navigate = useNavigate();
  const { principles, editTargetId, setEditTargetId, setDraft } = useApp();

  const [clarify, setClarify] = useState<Clarify | null>(null); // 서버가 되물을 때의 질문과 선택지
  const [history, setHistory] = useState<string[]>([]); // 되묻기 전까지 사용자가 한 말
  const [pending, setPending] = useState<string | null>(null); // 서버가 수치를 바꾸는 동안 보낸 말
  const base = principles.find((p) => p.id === editTargetId);
  const [lockedIds, setLockedIds] = useState<number[]>(() => lockedOf(base)); // 잠근 지표 id. 대화로 수정할 때 서버에 보내 수치를 지킨다.
  const [sheetOpen, setSheetOpen] = useState(false); // "내가 설정한 지표값 상세" 시트
  const [edited, setEdited] = useState<Principle | null>(null); // 수치를 직접 고친 원칙 (저장 전)
  const view = edited ?? base; // 화면에 보여주는 원칙

  // 고치려는 원칙을 바꾸면 그 원칙에 저장된 잠금으로 다시 시작한다
  useEffect(() => {
    setLockedIds(lockedOf(base));
    setSheetOpen(false);
    setEdited(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editTargetId]);

  // 수치를 직접 입력하면 그 지표는 내가 정한 지표(user)가 된다. 목록 순서는 처음 원칙 기준이라 입력 중에 카드가 움직이지 않는다.
  function editValue(id: number, text: string, n: number) {
    setEdited({
      ...view!,
      values: { ...view!.values, [id]: text },
      indicators: view!.indicators.map((i) => (i.id === id ? { ...i, value: n, source: "user" } : i)),
    });
  }

  // 고친 수치를 02-2로 가져가 확인·저장한다
  function continueEdited() {
    setDraft({ ...edited!, indicators: edited!.indicators.map((i) => ({ ...i, locked: lockedIds.includes(i.id) })) });
    navigate("/setup-edit");
  }

  function toggleLock(id: number) {
    setLockedIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }

  // 잠근 지표 먼저, 그다음 내가 정한 지표, 마지막에 기본값 지표
  const sorted = base
    ? [...base.indicators].sort((a, b) => rank(a, lockedIds) - rank(b, lockedIds) || a.id - b.id)
    : [];

  // 되묻는 중이면 앞서 한 말을 history로 함께 보내, 선택지 답이 무엇에 대한 것인지 서버가 알게 한다.
  async function modify(text: string) {
    setPending(text);
    const result = await askPrinciple(text, view!, lockedIds, history);
    setPending(null);
    if (result.needsClarify || !result.principle) {
      setClarify(result.clarify);
      setHistory([...history, text]);
      return;
    }
    setClarify(null);
    setHistory([]);
    // 모델 응답과 상관없이 잠긴 지표는 기존 수치를 그대로 유지한다
    const values = { ...result.principle.values };
    for (const id of lockedIds) values[id] = view!.values[id];
    setDraft({ ...result.principle, values, id: base!.id, name: base!.name });
    navigate("/setup-edit");
  }

  return (
    <div className="screen tall-gap">
      <div className="top-bar">
        <button className="back" onClick={() => navigate(-1)} aria-label="뒤로 가기">
          <img src={back} width={24} height={24} alt="" />
        </button>
        <h1 className="title s08-title">원칙 수정하기</h1>
      </div>
      <h3 className="label">원칙을 선택하세요</h3>
      <Select principles={principles} value={editTargetId} onChange={setEditTargetId} />
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
      {clarify && <ChatBubble side="ai">{clarify.message}</ChatBubble>}
      {clarify && pending === null && (
        <div className="options">
          {clarify.options.map((o) => (
            <Chip key={o.label} onClick={() => modify(o.label)}>{o.label}</Chip>
          ))}
        </div>
      )}
      <div className="spacer" />
      {pending !== null && (
        <div className="chat-wait">
          <ChatBubble side="user">{pending}</ChatBubble>
          <ChatBubble side="ai"><span className="typing"><span className="dots"><i /><i /><i /></span>수치를 바꿔 보는 중이에요</span></ChatBubble>
        </div>
      )}
      {!clarify && pending === null && (
        <div className="chip-row">
          {suggestions.map((s) => (
            <Chip key={s} onClick={() => modify(s)}>{s}</Chip>
          ))}
        </div>
      )}
      <ChatInput placeholder="바꾸고 싶은 점을 말해 보세요" busy={pending !== null} busyText="수치를 바꿔 보는 중이에요" onSend={modify} />
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
                value={view!.values[i.id]}
                locked={lockedIds.includes(i.id)}
                onToggleLock={() => toggleLock(i.id)}
                onEditValue={(text, n) => editValue(i.id, text, n)}
                tag={view!.indicators.find((x) => x.id === i.id)!.source === "default" ? "default" : "user"}
              />
            ))}
          </div>
        </div>
        {edited ? <Button onClick={continueEdited}>수정한 수치로 이어서 확인</Button> : <Button onClick={() => setSheetOpen(false)}>닫기</Button>}
      </BottomSheet>
    </div>
  );
}
