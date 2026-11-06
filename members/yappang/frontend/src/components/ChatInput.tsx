import { useState } from "react";
import send from "../assets/icons/send.svg";

type Props = {
  placeholder?: string;
  size?: "md" | "sm"; // sm: 02 원칙 세팅 하단 입력창 (높이 52)
  onSend: (text: string) => void;
};

export default function ChatInput({ placeholder = "원칙을 말해 주세요", size = "md", onSend }: Props) {
  const [text, setText] = useState("");

  function submit() {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  }

  return (
    <div className={`chat-input ${size}`}>
      <input
        value={text}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
      />
      <button onClick={submit} aria-label="보내기">
        <img src={send} width={20} height={20} alt="" />
      </button>
    </div>
  );
}
