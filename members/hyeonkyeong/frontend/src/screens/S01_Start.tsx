import { Navigate, useNavigate } from "react-router-dom";
import { askPrinciple } from "../api";
import ChatInput from "../components/ChatInput";
import Chip from "../components/Chip";
import { useApp } from "../store/AppContext";

const suggestions = [
  "빚 많은 회사는 피하고 싶어",
  "배당 꾸준한 곳이 좋아",
  "너무 비싼 주식은 싫어요",
  "적자 기업은 제외할래요",
  "성장하는 회사만 보고 싶어",
];

export default function S01_Start() {
  const navigate = useNavigate();
  const { principles, setUserText, setDraft, setClarify } = useApp();

  // 이미 원칙이 있는 사용자는 시작 화면 없이 종목 검색으로 간다
  if (principles.length > 0) return <Navigate to="/stocks" replace />;

  async function start(text: string) {
    const result = await askPrinciple(text);
    setUserText(text);
    setDraft(result.principle);
    setClarify(result.clarify);
    navigate(result.needsClarify ? "/clarify" : "/setup");
  }

  return (
    <div className="screen s01">
      <div className="logo">StockRuleKeeper</div>
      <div className="s01-center">
        <div className="guide">
          <h1 className="headline">{"어떤 원칙으로\n투자하고 싶으세요?"}</h1>
          <p className="s01-desc">평소 생각하는 대로 편하게 말해 주세요. 제가 숫자 기준으로 바꿔 드려요.</p>
        </div>
        <div className="s01-input">
          <ChatInput placeholder="지키고 싶은 투자 원칙을 말해 보세요" onSend={start} />
          <div className="chip-row">
            {suggestions.map((s) => (
              <Chip key={s} onClick={() => start(s)}>{s}</Chip>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
