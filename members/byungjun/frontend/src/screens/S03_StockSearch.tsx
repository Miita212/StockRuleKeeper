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
  const found = searching ? stocks.filter((s) => s.name.includes(query) || s.code.includes(query)) : recs;

  // 서버가 충족 지표가 많은 순으로 보내 준다. 15개씩 페이지로 나눠 보여 준다.
  const PAGE_SIZE = 15;
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(found.length / PAGE_SIZE));
  const shown = found.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="screen s03">
      <h1 className="title">종목 검색</h1>
      <div className="search">
        <img src={search} width={22} height={22} alt="" />
        <input value={query} placeholder="종목명이나 코드를 검색해요" onChange={(e) => { setQuery(e.target.value); setPage(1); }} />
      </div>
      <p className="note">반도체 업종 종목만 점검할 수 있어요.</p>
      <div className="list-header">
        <h3 className="label">{searching ? "검색 결과" : "내 원칙에 맞는 반도체 종목"}</h3>
        <span>{found.length}개</span>
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
      {pageCount > 1 && (
        <div className="pager">
          {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
            <button key={n} className={n === page ? "on" : ""} onClick={() => setPage(n)}>{n}</button>
          ))}
        </div>
      )}
    </div>
  );
}
