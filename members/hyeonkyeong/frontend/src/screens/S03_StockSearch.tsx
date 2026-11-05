import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { recommendStocks, searchStocks } from "../api";
import search from "../assets/icons/search.svg";
import { useApp } from "../store/AppContext";
import type { Stock } from "../types";

export default function S03_StockSearch() {
  const navigate = useNavigate();
  const { principles, currentId } = useApp();
  const principle = principles.find((p) => p.id === currentId)!;
  const total = Object.keys(principle.values).length;
  const [stocks, setStocks] = useState<Stock[]>([]); // 검색용 전체 종목
  const [recs, setRecs] = useState<Stock[]>([]); // 검색창 아래 추천(원칙을 모두 충족)
  const [query, setQuery] = useState("");

  useEffect(() => {
    searchStocks(principle).then(setStocks);
    recommendStocks(principle).then(setRecs);
  }, [principle]);

  // 검색어가 없으면 추천 종목, 있으면 전체 종목에서 검색
  const searching = query.trim() !== "";
  const shown = searching ? stocks.filter((s) => s.name.includes(query) || s.code.includes(query)) : recs;

  return (
    <div className="screen s03">
      <h1 className="title">종목 검색</h1>
      <div className="search">
        <img src={search} width={22} height={22} alt="" />
        <input value={query} placeholder="종목명이나 코드를 검색해요" onChange={(e) => setQuery(e.target.value)} />
      </div>
      <p className="note">반도체 업종 종목만 점검할 수 있어요.</p>
      <div className="list-header">
        <h3 className="label">{searching ? "검색 결과" : "내 원칙에 맞는 반도체 종목"}</h3>
        <span>{shown.length}개</span>
      </div>
      {!searching && recs.length === 0 && (
        <p className="note">지금 원칙을 모두 충족하는 종목이 없어요. 종목을 검색하면 판정서를 볼 수 있어요.</p>
      )}
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
