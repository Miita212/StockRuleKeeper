import { useState } from "react";
import send from "../assets/icons/send.svg";

type Props = {
  placeholder?: string;
  size?: "md" | "sm"; // sm: 02 원칙 세팅 하단 입력창 (높이 52)
  busy?: boolean; // 서버 응답을 기다리는 중: 입력을 막고 보내기 버튼을 스피너로
  busyText?: string; // 기다리는 동안 입력창에 보여줄 문구
  locked?: boolean; // 위의 선택 버튼을 먼저 골라야 하는 중: 입력을 막고 안내 문구를 보여준다
  lockedText?: string;
  onSend: (text: string) => void;
};

export default function ChatInput({ placeholder = "원칙을 말해 주세요", size = "md", busy = false, busyText = "", locked = false, lockedText = "", onSend }: Props) {
  const [text, setText] = useState("");
  const off = busy || locked;

  function submit() {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  }

  return (
    <div className={`chat-input ${size}${busy ? " busy" : ""}${locked ? " locked" : ""}`}>
      <input
        value={text}
        placeholder={busy ? busyText : locked ? lockedText : placeholder}
        disabled={off}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
      />
      <button onClick={submit} disabled={off} aria-label="보내기">
        {busy ? <span className="spinner" /> : <img src={send} width={20} height={20} alt="" />}
      </button>
    </div>
  );
}
