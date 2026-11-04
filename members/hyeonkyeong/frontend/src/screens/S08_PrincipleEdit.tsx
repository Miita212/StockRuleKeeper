import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { askPrinciple } from "../api";
import back from "../assets/icons/back.svg";
import ChatInput from "../components/ChatInput";
import ChatBubble from "../components/ChatBubble";
import Chip from "../components/Chip";
import Select from "../components/Select";
import { useApp } from "../store/AppContext";

const suggestions = ["부채비율을 더 낮춰 줘", "배당 기준을 올려 줘", "성장성도 보고 싶어", "조건을 조금 느슨하게 해 줘"];

export default function S08_PrincipleEdit() {
  const navigate = useNavigate();
  const { principles, editTargetId, setEditTargetId, setDraft } = useApp();

  const [notice, setNotice] = useState(""); // 서버가 되물을 때의 안내

  async function modify(text: string) {
    const base = principles.find((p) => p.id === editTargetId)!;
    const result = await askPrinciple(text, base);
    if (result.needsClarify || !result.principle) {
      setNotice(result.clarify?.message ?? "");
      return;
    }
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
      {notice && <ChatBubble side="ai">{notice}</ChatBubble>}
      <div className="spacer" />
      <div className="chip-row">
        {suggestions.map((s) => (
          <Chip key={s} onClick={() => modify(s)}>{s}</Chip>
        ))}
      </div>
      <ChatInput placeholder="바꾸고 싶은 점을 말해 보세요" onSend={modify} />
    </div>
  );
}
