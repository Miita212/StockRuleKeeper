import type { ReactNode } from "react";
import { boldIndicators } from "../data/boldIndicators";

type Props = {
  side: "ai" | "user";
  size?: "md" | "sm"; // sm: 02 원칙 세팅의 작은 말풍선
  children: ReactNode;
};

export default function ChatBubble({ side, size = "md", children }: Props) {
  return <div className={`bubble bubble-${side} bubble-${size}`}>{side === "ai" && typeof children === "string" ? boldIndicators(children) : children}</div>;
}
