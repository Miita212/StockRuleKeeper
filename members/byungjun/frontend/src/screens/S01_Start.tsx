import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
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
  const location = useLocation();
  const { principles, setUserText, setDraft, setClarify } = useApp();
  const [waiting, setWaiting] = useState<string | null>(null); // 서버가 원칙을 바꾸는 동안 보낸 문장

  // 앱을 켰을 때 이미 원칙이 있으면 종목 검색으로 간다 (하단 [원칙 생성] 탭으로 온 경우는 새 원칙을 만든다)
  const fromNav = location.state?.fromNav;
  if (principles.length > 0 && !fromNav) return <Navigate to="/stocks" replace />;

  async function start(text: string) {
    setWaiting(text);
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
          <ChatInput placeholder="지키고 싶은 투자 원칙을 말해 보세요" busy={waiting !== null} busyText={waiting ?? ""} onSend={start} />
          {waiting === null ? (
            <div className="chip-row">
              {suggestions.map((s) => (
                <Chip key={s} onClick={() => start(s)}>{s}</Chip>
              ))}
            </div>
          ) : (
            <div className="s01-wait">
              <div className="typing"><span className="dots"><i /><i /><i /></span>원칙을 숫자 기준으로 바꾸는 중이에요</div>
              <p className="note">보통 몇 초 걸려요. 잠시만 기다려 주세요.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
