import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { searchStocks } from "../api";
import search from "../assets/icons/search.svg";
import { useApp } from "../store/AppContext";
import type { Stock } from "../types";

export default function S03_StockSearch() {
  const navigate = useNavigate();
  const { principles, currentId } = useApp();
  const principle = principles.find((p) => p.id === currentId)!;
  const total = Object.keys(principle.values).length;
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    searchStocks(principle).then(setStocks);
  }, [principle]);

  const shown = stocks.filter((s) => s.name.includes(query) || s.code.includes(query));

  return (
    <div className="screen s03">
      <h1 className="title">종목 검색</h1>
      <div className="search">
        <img src={search} width={22} height={22} alt="" />
        <input value={query} placeholder="종목명이나 코드를 검색해요" onChange={(e) => setQuery(e.target.value)} />
      </div>
      <p className="note">반도체 업종 종목만 점검할 수 있어요.</p>
      <div className="list-header">
        <h3 className="label">내 원칙에 맞는 반도체 종목</h3>
        <span>{shown.length}개</span>
      </div>
      <div className="list">
        {shown.map((s) => (
          <div key={s.code} className="stock-card" onClick={() => navigate(`/stocks/${s.code}`)}>
            <div className="indicator-text">
              <div className="indicator-name">{s.name}</div>
              <div className="stock-sub">{s.code} · 원칙 {s.passCount}/{total}개 충족</div>
            </div>
            <div className={`rate ${s.changeRate >= 0 ? "up" : "down"}`}>
              {s.changeRate >= 0 ? "▲" : "▼"} {Math.abs(s.changeRate)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
