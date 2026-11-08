import { useRef, type MouseEvent, type PointerEvent } from "react";

// 화면을 오른쪽에서 왼쪽으로 밀면 다음 페이지, 왼쪽에서 오른쪽으로 밀면 이전 페이지.
// 반환값을 페이지를 감싸는 요소에 펼쳐서(...) 쓴다. 밀고 난 뒤 이어지는 클릭은 막아서 카드가 열리지 않게 한다.
export default function usePageSwipe(onNext: () => void, onPrev: () => void) {
  const start = useRef<{ x: number; y: number } | null>(null);
  const swiped = useRef(false);
  return {
    onPointerDown: (e: PointerEvent) => {
      start.current = { x: e.clientX, y: e.clientY };
      swiped.current = false;
    },
    onPointerUp: (e: PointerEvent) => {
      if (!start.current) return;
      const dx = e.clientX - start.current.x;
      const dy = e.clientY - start.current.y;
      start.current = null;
      if (Math.abs(dx) > 60 && Math.abs(dx) > 2 * Math.abs(dy)) {
        swiped.current = true;
        if (dx < 0) onNext();
        else onPrev();
      }
    },
    onClickCapture: (e: MouseEvent) => {
      if (swiped.current) {
        e.stopPropagation();
        e.preventDefault();
        swiped.current = false;
      }
    },
  };
}
