import type { ReactNode } from "react";

type Props = {
  variant?: "primary" | "secondary";
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
};

export default function Button({ variant = "primary", disabled, onClick, children }: Props) {
  return (
    <button
      className={`btn btn-${disabled ? "disabled" : variant}`}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
