import { useEffect, useRef } from "react";

const SPEED = 30; // 초당 이동 px
const PAUSE = 3; // 끝에서 멈춰 있는 시간(초). 이 시간이 지나면 처음으로 돌아가 다시 시작한다

// 칸보다 긴 글자만 오른쪽→왼쪽으로 흘러 마지막 글자가 칸 오른쪽 끝에 닿으면 멈춘다. 짧으면 그대로 둔다.
export default function ScrollText({ text }: { text: string }) {
  const box = useRef<HTMLSpanElement>(null);
  const inner = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const shift = inner.current!.scrollWidth - box.current!.clientWidth;
    if (shift <= 0) return;
    const move = shift / SPEED;
    const anim = inner.current!.animate(
      [
        { transform: "translateX(0)", offset: 0 },
        { transform: `translateX(-${shift}px)`, offset: move / (move + PAUSE) },
        { transform: `translateX(-${shift}px)`, offset: 1 },
      ],
      { duration: (move + PAUSE) * 1000, iterations: Infinity, easing: "linear" },
    );
    return () => anim.cancel();
  }, [text]);

  return (
    <span ref={box} className="scroll-text">
      <span ref={inner}>{text}</span>
    </span>
  );
}
