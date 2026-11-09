// 화면 맨 위 공지사항 띠: 문구가 오른쪽에서 나타나 왼쪽으로 계속 흘러간다. (03 종목 검색)
export default function NoticeBar({ children }: { children: string }) {
  return (
    <div className="notice-bar" role="status">
      <span>{children}</span>
    </div>
  );
}
