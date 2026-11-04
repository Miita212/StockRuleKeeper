// 시뮬레이션 헤더 오른쪽 단계 표시 (4단계, current는 0부터)
export default function Steps({ current }: { current: number }) {
  return (
    <div className="steps">
      {[0, 1, 2, 3].map((i) => (
        <span key={i} className={i === current ? "current" : ""} />
      ))}
    </div>
  );
}
