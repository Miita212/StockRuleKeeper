type Props = {
  selected?: boolean;
  onClick?: () => void;
  children: string;
};

export default function Chip({ selected, onClick, children }: Props) {
  return (
    <button className={`chip ${selected ? "chip-selected" : ""}`} onClick={onClick}>
      {children}
    </button>
  );
}
