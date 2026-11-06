// 페이지 이동 버튼 "‹ 1 / 3 ›". 03 종목 검색과 06 원칙 리스트가 같이 쓴다.
export default function Pager({ page, pageCount, onChange }: { page: number; pageCount: number; onChange: (page: number) => void }) {
  return (
    <div className="pager">
      <button aria-label="이전 페이지" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹</button>
      <span>{page} / {pageCount}</span>
      <button aria-label="다음 페이지" disabled={page >= pageCount} onClick={() => onChange(page + 1)}>›</button>
    </div>
  );
}
