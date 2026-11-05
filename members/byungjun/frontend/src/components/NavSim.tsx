import { Link, useLocation } from "react-router-dom";
import menu from "../assets/nav/menu.svg";
import principles from "../assets/nav/principles.svg";
import principlesActive from "../assets/nav/principles-active.svg";
import stocks from "../assets/nav/stocks.svg";
import stocksActive from "../assets/nav/stocks-active.svg";

// 3단 하단 바 (Nav/Sim)
export default function NavSim() {
  const { pathname } = useLocation();
  const individual = pathname === "/sim/individual";

  return (
    <nav className="nav">
      <Link to="/sim-menu">
        <img src={menu} width={24} height={24} alt="" />
        메뉴로 돌아가기
      </Link>
      <Link to="/sim/individual" className={individual ? "active" : ""}>
        <img src={individual ? stocksActive : stocks} width={24} height={24} alt="" />
        개별 종목
      </Link>
      <Link to="/sim" className={individual ? "" : "active"}>
        <img src={individual ? principles : principlesActive} width={24} height={24} alt="" />
        원칙 커스터마이징
      </Link>
    </nav>
  );
}
