import { useNavigate } from "react-router-dom";
import Button from "../components/Button";
import Select from "../components/Select";
import Steps from "../components/Steps";
import { summarize } from "../data/indicators";
import { useApp } from "../store/AppContext";

// 10 (3단 바)과 10-1 (5단 바) 공용. 하단 바는 레이아웃이 정한다.
export default function S10_SimSelect() {
  const navigate = useNavigate();
  const { principles, simPrincipleId, setSimPrincipleId, setSimValues } = useApp();
  const principle = principles.find((p) => p.id === simPrincipleId)!;

  function next() {
    setSimValues({ ...principle.values });
    navigate("/sim/adjust");
  }

  return (
    <div className="screen tall-gap">
      <div className="header">
        <h1 className="title s-sim-title">시뮬레이션</h1>
        <Steps current={0} />
      </div>
      <div className="guide s-sim-guide">
        <h2 className="headline">{"어떤 원칙으로\n시뮬레이션 해볼까요?"}</h2>
        <p className="desc">원칙을 고르면 수치를 바꿔서 과거에 어땠을지 비교해 볼 수 있어요. (반도체 업종 종목 기준)</p>
      </div>
      <h3 className="label s10-label">원칙을 선택하세요</h3>
      <Select principles={principles} value={simPrincipleId} onChange={setSimPrincipleId} strong />
      <p className="note">{summarize(principle)}</p>
      <div className="spacer" />
      <Button onClick={next}>다음</Button>
    </div>
  );
}
