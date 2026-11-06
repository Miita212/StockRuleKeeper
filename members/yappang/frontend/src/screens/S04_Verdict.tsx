import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { getVerdict } from "../api";
import check from "../assets/icons/check.svg";
import x from "../assets/icons/x.svg";
import Button from "../components/Button";
import { categoryLabel, groupByCategory } from "../data/indicators";
import { useApp } from "../store/AppContext";
import type { Verdict } from "../types";

export default function S04_Verdict() {
  const navigate = useNavigate();
  const { code } = useParams();
  const stockName: string | undefined = useLocation().state?.name; // 03에서 넘어올 때 받은 종목 이름
  const { principles, currentId } = useApp();
  const principle = principles.find((p) => p.id === currentId)!;
  const [verdict, setVerdict] = useState<Verdict | null>(null);

  useEffect(() => {
    getVerdict(code!, principle).then(setVerdict);
  }, [code, principle]);

  if (!verdict) {
    return (
      <div className="screen with-footer s04">
        <h1 className="title">판정서</h1>
        <div className="verdict-card">
          <div className="verdict-head">
            <div>
              <span className="name">{stockName}</span>
              <span className="stock-code">{code}</span>
            </div>
            <span className="skeleton" style={{ width: 64, height: 22 }} />
          </div>
          <div className="summary waiting">
            <span>최신 값으로 판정하는 중이에요</span>
            <span className="skeleton" style={{ width: 84, height: 32, borderRadius: 8 }} />
          </div>
          <div className="scroll">
            {Array.from({ length: 8 }, (_, n) => (
              <div key={n} className="verdict-row skeleton-row">
                <span className="skeleton circle" />
                <div className="indicator-text">
                  <span className="skeleton" style={{ width: 100, height: 14 }} />
                  <span className="skeleton" style={{ width: 70, height: 10 }} />
                </div>
                <span className="skeleton" style={{ width: 48, height: 18 }} />
              </div>
            ))}
          </div>
        </div>
        <Button variant="secondary" onClick={() => navigate("/stocks")}>닫기</Button>
      </div>
    );
  }

  const passed = verdict.rows.filter((r) => r.pass).length;
  const { stock } = verdict;
  const groups = groupByCategory(verdict.rows.map((r) => r.indicatorId));

  return (
    <div className="screen with-footer s04">
      <h1 className="title">판정서</h1>
      <div className="verdict-card">
        <div className="verdict-head">
          <div>
            <span className="name">{stock.name}</span>
            <span className="stock-code">{stock.code}</span>
          </div>
          <div className="rate-box">
            <span className={`rate ${stock.changeRate >= 0 ? "up" : "down"}`}>
              {stock.changeRate >= 0 ? "▲" : "▼"} {Math.abs(stock.changeRate)}%
            </span>
            <span className="today">오늘</span>
          </div>
        </div>
        <div className="summary">
          <span>투자 원칙을 만족해요</span>
          <div>
            <span className="score">{passed}</span>
            <span className="total"> / {verdict.rows.length}개</span>
          </div>
        </div>
        <div className="scroll">
          {groups.map(([category, items]) => [
            <h3 key={category} className="category">{categoryLabel(category, items.length)}</h3>,
            ...items.map((i) => {
              const row = verdict.rows.find((r) => r.indicatorId === i.id)!;
              return (
                <div key={i.id} className={`verdict-row ${row.pass ? "pass" : "fail"}`}>
                  <div className="verdict-icon">
                    <img src={row.pass ? check : x} width={20} height={20} alt="" />
                  </div>
                  <div className="indicator-text">
                    <div className="indicator-name">{i.name}</div>
                    <div className="indicator-desc">기준 {row.criterion}</div>
                  </div>
                  <div className="verdict-value">
                    <b>{row.actual}</b>
                    <span>{row.pass ? "충족" : "미충족"}</span>
                  </div>
                </div>
              );
            }),
          ])}
        </div>
      </div>
      <Button variant="secondary" onClick={() => navigate("/stocks")}>닫기</Button>
    </div>
  );
}
