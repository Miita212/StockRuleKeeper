import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { runSimulation } from "../api";
import Button from "../components/Button";
import Steps from "../components/Steps";
import { useApp } from "../store/AppContext";

const periods = [3, 6, 12]; // 서버가 계산하는 기간

export default function S12_SimPeriod() {
  const navigate = useNavigate();
  const { principles, simPrincipleId, simValues, months, setMonths, setSimResult } = useApp();
  const [running, setRunning] = useState(false);
  const [failed, setFailed] = useState(false);

  // 서버가 계산하고 리포트를 쓰는 데 10~15초 걸린다
  async function start() {
    const principle = principles.find((p) => p.id === simPrincipleId)!;
    const lockedIds = principle.indicators.filter((i) => i.locked).map((i) => i.id);
    setRunning(true);
    setFailed(false);
    try {
      setSimResult(await runSimulation(principle, simValues, months, lockedIds));
      navigate("/sim/report");
    } catch {
      setFailed(true);
      setRunning(false);
    }
  }

  return (
    <div className="screen tall-gap">
      <div className="header">
        <h1 className="title s-sim-title">시뮬레이션</h1>
        <Steps current={2} />
      </div>
      <div className="guide s-sim-guide">
        <h2 className="headline">{"얼마 동안\n시뮬레이션 해볼까요?"}</h2>
        <p className="desc">시뮬레이션 기간을 설정하세요. 선택한 기간 동안 이 원칙대로 종목을 골랐다면 어땠을지 계산해요.</p>
      </div>
      <div className="segment">
        {periods.map((m) => (
          <button key={m} className={m === months ? "selected" : ""} onClick={() => setMonths(m)}>
            {m}개월
          </button>
        ))}
      </div>
      <p className="note">
        {failed ? "계산하지 못했어요. 서버 연결을 확인하고 다시 눌러 주세요." : `지금 ${months}개월로 설정돼 있어요.`}
      </p>
      <div className="spacer" />
      <Button disabled={running} onClick={start}>
        {running ? "계산하는 중이에요 (10~15초)" : "시뮬레이션 시작"}
      </Button>
    </div>
  );
}
