import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { runSimulation } from "../api";
import Button from "../components/Button";
import Steps from "../components/Steps";
import { useApp } from "../store/AppContext";

const periods = [3, 6, 12]; // 서버가 계산하는 기간

// 계산 중에 보여주는 단계. 서버가 진행률을 주지 않아서 시간이 지나면 다음 단계로 넘어간다.
const steps = [
  { doing: "원칙 기준으로 종목을 고르고 있어요", done: "원칙 기준으로 종목을 골랐어요" },
  { doing: "전·후 수익률을 계산하고 있어요", done: "전·후 수익률을 계산했어요" },
  { doing: "리포트를 쓰고 있어요", done: "리포트를 썼어요" },
];

export default function S12_SimPeriod() {
  const navigate = useNavigate();
  const { principles, simPrincipleId, simValues, months, setMonths, setSimResult } = useApp();
  const [running, setRunning] = useState(false);
  const [failed, setFailed] = useState(false);
  const [step, setStep] = useState(0); // 지금 하고 있는 단계

  useEffect(() => {
    setStep(0);
    if (!running) return;
    const t1 = setTimeout(() => setStep(1), 2000);
    const t2 = setTimeout(() => setStep(2), 6000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [running]);

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
      <div className={`segment${running ? " busy" : ""}`}>
        {periods.map((m) => (
          <button key={m} className={m === months ? "selected" : ""} onClick={() => setMonths(m)}>
            {m}개월
          </button>
        ))}
      </div>
      <p className="note">
        {failed
          ? "계산하지 못했어요. 서버 연결을 확인하고 다시 눌러 주세요."
          : running
            ? `${months}개월 기준으로 계산하고 있어요.`
            : `지금 ${months}개월로 설정돼 있어요.`}
      </p>
      {running && (
        <div className="sim-progress">
          <div>
            <h3>시뮬레이션을 계산하고 있어요</h3>
            <p>보통 10~15초 걸려요</p>
          </div>
          <div className="progress-bar"><i style={{ width: `${(step + 1) * 25}%` }} /></div>
          <div className="progress-steps">
            {steps.map((s, i) => (
              <div key={s.doing} className={`progress-step ${i < step ? "done" : i === step ? "active" : "pending"}`}>
                <span className="step-mark">{i < step ? "✓" : i === step ? <span className="spinner" /> : null}</span>
                {i < step ? s.done : s.doing}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="spacer" />
      <Button disabled={running} onClick={start}>
        {running ? "계산하는 중이에요" : "시뮬레이션 시작"}
      </Button>
    </div>
  );
}
