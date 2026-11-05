import { BottomSheet as TdsBottomSheet } from "@toss/tds-mobile";
import type { ReactNode } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
};

// 팝업 계열은 TDS 컴포넌트를 쓴다 (검수 권장). 교체는 이 파일 안에서만.
// 시트는 390x844 프레임(.app) 안에 띄운다. .app의 transform이 fixed 위치의 기준이 된다.
export default function BottomSheet({ open, onClose, children }: Props) {
  return (
    <TdsBottomSheet
      open={open}
      onClose={onClose}
      portalContainer={document.querySelector<HTMLElement>(".app") ?? undefined}
    >
      <div className="sheet-body">{children}</div>
    </TdsBottomSheet>
  );
}
