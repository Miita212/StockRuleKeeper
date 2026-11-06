import { ConfirmDialog as TdsConfirmDialog } from "@toss/tds-mobile";

type Props = {
  open: boolean;
  title: string;
  description: string;
  confirmText: string;
  onConfirm: () => void;
  onClose: () => void;
};

// 확인 창도 TDS 컴포넌트를 쓴다. 교체는 이 파일 안에서만. 390x844 프레임(.app) 안에 띄운다.
export default function ConfirmDialog({ open, title, description, confirmText, onConfirm, onClose }: Props) {
  return (
    <TdsConfirmDialog
      open={open}
      title={title}
      description={description}
      onClose={onClose}
      portalContainer={document.querySelector<HTMLElement>(".app") ?? undefined}
      cancelButton={<TdsConfirmDialog.CancelButton onClick={onClose}>취소</TdsConfirmDialog.CancelButton>}
      confirmButton={<TdsConfirmDialog.ConfirmButton color="danger" onClick={onConfirm}>{confirmText}</TdsConfirmDialog.ConfirmButton>}
    />
  );
}
