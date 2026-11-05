import { useNavigate } from "react-router-dom";
import Button from "../components/Button";
import Steps from "../components/Steps";
import { useApp } from "../store/AppContext";

// 종합 리포트 (project_details/07 스키마). 숫자는 서버 코드가 계산하고 문장만 LLM이 쓴다.
export default function S13_SimReport() {
  const navigate = useNavigate();
  const { simResult } = useApp();
  const report = simResult?.report;

  return (
    <div className="screen with-footer tall-gap">
      <div className="header">
        <h1 className="title s-sim-title">시뮬레이션</h1>
        <Steps current={3} />
      </div>
      {!simResult || !report ? (
        <div className="scroll">
          <p className="note">리포트가 아직 없어요. 시뮬레이션을 먼저 실행해 주세요.</p>
        </div>
      ) : (
        <div className="scroll">
          <h2 className="report-headline">{report.headline}</h2>
          <p className="note">
            반도체 업종 {simResult.universeSize}개 종목 · {simResult.period.start} ~ {simResult.period.end} ({simResult.months}개월)
          </p>
          <div className="report-card">
            <b>무엇을 바꿨나요</b>
            <p>{report.what_changed}</p>
          </div>
          <div className="report-card">
            <b>바꾸기 전 · 후 비교</b>
            {report.comparison.map((c) => (
              <div key={c.label} className="compare-row">
                <div className="compare-label">{c.label}</div>
                <div className="compare-values">
                  <span>{c.before}</span>
                  <span className="arrow">→</span>
                  <span className="after">{c.after}</span>
                </div>
                <div className="compare-note">{c.note}</div>
              </div>
            ))}
          </div>
          <div className="report-card">
            <b>종목은 어떻게 달라졌나요</b>
            <p>{report.stock_changes}</p>
          </div>
          <div className="report-card caution">
            <b>꼭 알아 두세요</b>
            <ul>{report.cautions.map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
          <div className="report-card">
            <b>스스로 생각해 보세요</b>
            <ul>{report.think_about.map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
          {simResult.reportSource === "template" && (
            <p className="note">리포트 문장 생성에 실패해서 기본 문장으로 보여 드려요. 숫자는 같아요.</p>
          )}
        </div>
      )}
      <Button variant="secondary" onClick={() => navigate("/sim")}>다시 해보기</Button>
    </div>
  );
}
