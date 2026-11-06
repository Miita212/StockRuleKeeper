import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { askPrinciple } from "../api";
import back from "../assets/icons/back.svg";
import ChatInput from "../components/ChatInput";
import ChatBubble from "../components/ChatBubble";
import Chip from "../components/Chip";
import Select from "../components/Select";
import { useApp } from "../store/AppContext";
import type { Clarify } from "../types";

const suggestions = ["부채비율을 더 낮춰 줘", "배당 기준을 올려 줘", "성장성도 보고 싶어", "조건을 조금 느슨하게 해 줘"];

export default function S08_PrincipleEdit() {
  const navigate = useNavigate();
  const { principles, editTargetId, setEditTargetId, setDraft } = useApp();

  const [clarify, setClarify] = useState<Clarify | null>(null); // 서버가 되물을 때의 질문과 선택지
  const [history, setHistory] = useState<string[]>([]); // 되묻기 전까지 사용자가 한 말
  const [pending, setPending] = useState<string | null>(null); // 서버가 수치를 바꾸는 동안 보낸 말

  // 되묻는 중이면 앞서 한 말을 history로 함께 보내, 선택지 답이 무엇에 대한 것인지 서버가 알게 한다.
  async function modify(text: string) {
    setPending(text);
    const base = principles.find((p) => p.id === editTargetId)!;
    const result = await askPrinciple(text, base, [], history);
    setPending(null);
    if (result.needsClarify || !result.principle) {
      setClarify(result.clarify);
      setHistory([...history, text]);
      return;
    }
    setClarify(null);
    setHistory([]);
    setDraft({ ...result.principle, id: base.id, name: base.name });
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
      <div className="guide s08-guide">
        <h2 className="headline-sm">{"어떻게 바꾸고\n싶으세요?"}</h2>
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
    </div>
  );
}
