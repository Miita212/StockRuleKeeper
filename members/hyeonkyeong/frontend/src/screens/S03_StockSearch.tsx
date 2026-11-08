import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { searchStocks } from "../api";
import search from "../assets/icons/search.svg";
import Pager from "../components/Pager";
import usePageSwipe from "../hooks/usePageSwipe";
import { useApp } from "../store/AppContext";
import type { Stock } from "../types";

export default function S03_StockSearch() {
  const navigate = useNavigate();
  const { principles, currentId } = useApp();
  const principle = principles.find((p) => p.id === currentId)!;
  const total = Object.keys(principle.values).length;
  const [all, setAll] = useState<Stock[]>([]); // 전체 종목(서버 DB 값, 즉시)
  const [found, setFound] = useState<Stock[]>([]); // 검색한 종목(서버가 한투 최신 값으로 계산)
  const [searchingNow, setSearchingNow] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    searchStocks(principle).then(setAll);
  }, [principle]);

  // 입력이 0.5초 멈추면 그 검색어만 서버에 보낸다
  useEffect(() => {
    const q = query.trim();
    if (q === "") {
      setFound([]);
      setSearchingNow(false);
      return;
    }
    let ignore = false;
    setSearchingNow(true);
    const timer = setTimeout(() => {
      searchStocks(principle, q).then((r) => {
        if (!ignore) {
          setFound(r);
          setSearchingNow(false);
        }
      });
    }, 500);
    return () => {
      ignore = true;
      clearTimeout(timer);
    };
  }, [principle, query]);

  // 검색어가 없으면 전체 종목, 있으면 검색 결과. 충족 지표 많은 순(서버 정렬)으로 6개씩 페이지.
  const searching = query.trim() !== "";
  const waiting = searching && searchingNow; // 한투 최신 값을 받는 중
  const list = searching ? found : all;
  const PAGE_SIZE = 6; // 스크롤 없이 한 화면에 들어가는 개수
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  const shown = list.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const swipe = usePageSwipe(() => setPage(Math.min(page + 1, pageCount)), () => setPage(Math.max(page - 1, 1)));

  return (
    <div className="screen s03 swipe-page" {...swipe}>
      <h1 className="title">종목 검색</h1>
      <div className="search">
        <img src={search} width={22} height={22} alt="" />
        <input value={query} placeholder="종목명이나 코드를 검색해요" onChange={(e) => { setQuery(e.target.value); setPage(1); }} />
        {waiting && <span className="spinner" />}
      </div>
      <p className="note">반도체 업종 종목만 점검할 수 있어요.</p>
      {waiting ? (
        <div className="list-header">
          <h3 className="label">한국투자증권에서 최신 값을 불러오는 중이에요</h3>
        </div>
      ) : (
        <div className="list-header">
          <h3 className="label">{searching ? "검색 결과" : "내 원칙 충족 순 반도체 종목"}</h3>
          <div className="count-pager">
            <span>{list.length}개</span>
            {pageCount > 1 && <Pager page={page} pageCount={pageCount} onChange={setPage} />}
          </div>
        </div>
      )}
      {searching && !waiting && list.length === 0 && <p className="note">검색한 종목이 없어요.</p>}
      {waiting ? (
        <div className="list">
          {[1, 0.7, 0.45].map((opacity) => (
            <div key={opacity} className="stock-card skeleton-card" style={{ opacity }}>
              <div className="indicator-text">
                <span className="skeleton" style={{ width: 110, height: 16 }} />
                <span className="skeleton" style={{ width: 170, height: 12 }} />
              </div>
              <span className="skeleton" style={{ width: 56, height: 18 }} />
            </div>
          ))}
        </div>
      ) : (
      <div className="list">
        {shown.map((s) => (
          <div key={s.code} className="stock-card" onClick={() => navigate(`/stocks/${s.code}`, { state: { name: s.name } })}>
            <div className="indicator-text">
              <div className="indicator-name">{s.name}</div>
              <div className="stock-sub">{s.code} · 지표 {s.passCount}/{total}개 충족</div>
            </div>
            <div className={`rate ${s.changeRate >= 0 ? "up" : "down"}`}>
              {s.changeRate >= 0 ? "▲" : "▼"} {Math.abs(s.changeRate)}%
            </div>
          </div>
        ))}
      </div>
      )}
    </div>
  );
}
