import { useNavigate } from "react-router-dom";
import { askPrinciple } from "../api";
import ChatBubble from "../components/ChatBubble";
import ChatInput from "../components/ChatInput";
import Chip from "../components/Chip";
import { useApp } from "../store/AppContext";

export default function S02_1_Clarify() {
  const navigate = useNavigate();
  const { userText, clarify, setClarify, setDraft } = useApp();

  if (!clarify) return <div className="screen">되물을 내용이 없어요.</div>;

  // 선택지를 고르거나 직접 말하면, 처음 말과 함께 다시 보내 지표로 바꾼다. 또 되물으면 이 화면에 머문다.
  async function answer(text: string) {
    const result = await askPrinciple(text, undefined, [], [userText]);
    setClarify(result.clarify);
    if (result.needsClarify) return;
    setDraft(result.principle);
    navigate("/setup");
  }

  return (
    <div className="screen s02-1">
      <div className="logo s02-1-logo">StockRuleKeeper</div>
      <ChatBubble side="user">{userText}</ChatBubble>
      <ChatBubble side="ai">{clarify.message}</ChatBubble>
      <div className="options">
        {clarify.options.map((o) => (
          <Chip key={o.label} onClick={() => answer(o.label)}>{o.label}</Chip>
        ))}
      </div>
      <div className="spacer" />
      <ChatInput placeholder="직접 말해도 돼요" onSend={answer} />
    </div>
  );
}
