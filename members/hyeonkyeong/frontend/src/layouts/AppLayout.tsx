import { useEffect, useRef } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { latestShare } from "../api";
import NavMain from "../components/NavMain";
import NavSim from "../components/NavSim";
import { useApp } from "../store/AppContext";

// 하단 바는 여기서만 정한다.
// - 원칙이 하나도 없는 신규 사용자: 바 없음
// - 시뮬레이션(원칙 커스터마이징 흐름): 3단 바
// - 그 외: 5단 바
export default function AppLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { principles } = useApp();
  const hasPrinciples = principles.length > 0;
  const lastShareId = useRef<number | null>(null); // null: 아직 기준을 못 잡음

  // 가상 주식앱에서 "공유하기"를 누르면 그 종목의 판정서(04)로 이동한다 (2초마다 확인)
  useEffect(() => {
    if (!hasPrinciples) return;
    const timer = setInterval(async () => {
      try {
        const after = lastShareId.current ?? 0;
        const share = await latestShare(after);
        if (share) {
          const first = lastShareId.current === null; // 처음 확인에서 보이는 건 예전 공유라 무시
          lastShareId.current = share.id;
          if (!first) navigate(`/stocks/${share.code}`);
        } else if (lastShareId.current === null) {
          lastShareId.current = 0;
        }
      } catch {
        // 서버가 잠깐 안 닿으면 다음 확인 때 다시 시도한다
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [hasPrinciples, navigate]);

  const isSim = pathname.startsWith("/sim") && pathname !== "/sim-menu";
  const nav = isSim ? <NavSim /> : principles.length > 0 ? <NavMain /> : null;

  return (
    <>
      <div className={`content ${nav ? "with-nav" : ""}`}>
        <Outlet />
      </div>
      {nav}
    </>
  );
}
