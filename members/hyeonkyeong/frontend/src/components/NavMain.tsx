import { Link, useLocation } from "react-router-dom";
import create from "../assets/nav/create.svg";
import createActive from "../assets/nav/create-active.svg";
import principles from "../assets/nav/principles.svg";
import principlesActive from "../assets/nav/principles-active.svg";
import settings from "../assets/nav/settings.svg";
import settingsActive from "../assets/nav/settings-active.svg";
import sim from "../assets/nav/sim.svg";
import simActive from "../assets/nav/sim-active.svg";
import stocks from "../assets/nav/stocks.svg";
import stocksActive from "../assets/nav/stocks-active.svg";

// 5단 하단 바 (Nav/Main). active: 그 탭에 속하는 화면인지
const tabs = [
  { to: "/", label: "원칙 생성", icon: create, iconActive: createActive,
    active: (p: string) => ["/", "/clarify", "/setup"].includes(p) },
  { to: "/principles", label: "원칙 관리", icon: principles, iconActive: principlesActive,
    active: (p: string) => p.startsWith("/principles") || p === "/setup-edit" || p === "/edit-done" },
  { to: "/stocks", label: "종목 검색", icon: stocks, iconActive: stocksActive,
    active: (p: string) => p.startsWith("/stocks") },
  { to: "/sim", label: "시뮬레이션", icon: sim, iconActive: simActive,
    active: (p: string) => p === "/sim-menu" },
  { to: "/settings", label: "설정", icon: settings, iconActive: settingsActive,
    active: (p: string) => p === "/settings" },
];

export default function NavMain() {
  const { pathname } = useLocation();

  return (
    <nav className="nav">
      {tabs.map((t) => {
        const on = t.active(pathname);
        return (
          <Link key={t.to} to={t.to} className={on ? "active" : ""}>
            <img src={on ? t.iconActive : t.icon} width={24} height={24} alt="" />
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
