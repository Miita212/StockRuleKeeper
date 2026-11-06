import { useNavigate } from "react-router-dom";
import Button from "../components/Button";
import Steps from "../components/Steps";
import ValueInput from "../components/ValueInput";
import { categoryLabel, groupByCategory } from "../data/indicators";
import { useApp } from "../store/AppContext";

// "100% 이하" 같은 문자열의 첫 숫자만 step만큼 바꾼다
function change(value: string, step: number) {
  return value.replace(/-?[\d,]+(\.\d+)?/, (n) => {
    const next = Number(n.replace(/,/g, "")) + step;
    return Math.abs(next) >= 100 ? next.toLocaleString("en-US") : String(next);
  });
}

// "100% 이하" → ["100%", "이하"]. 방향 말이 없으면 ["흑자", ""]
function split(value: string) {
  const i = value.lastIndexOf(" ");
  return i < 0 ? [value, ""] : [value.slice(0, i), value.slice(i + 1)];
}

export default function S11_SimAdjust() {
  const navigate = useNavigate();
  const { principles, simPrincipleId, simValues, setSimValues } = useApp();
  const origin = principles.find((p) => p.id === simPrincipleId)!.values;
  const groups = groupByCategory(Object.keys(simValues).map(Number));

  function step(id: number, amount: number) {
    setSimValues({ ...simValues, [id]: change(simValues[id], amount) });
  }

  return (
    <div className="screen with-footer tall-gap">
      <div className="header">
        <h1 className="title s-sim-title">시뮬레이션</h1>
        <Steps current={1} />
      </div>
      <div className="guide s11-guide">
        <h2 className="headline-sm">원칙 수치를 수정하세요</h2>
        <p className="desc">+ − 나 숫자를 눌러 바꿔요. 바뀐 값은 파란색이에요.</p>
      </div>
      <div className="scroll">
        {groups.map(([category, items]) => [
          <h3 key={category} className="category">{categoryLabel(category, items.length)}</h3>,
          ...items.map((i) => {
            const edited = simValues[i.id] !== origin[i.id];
            const [, direction] = split(simValues[i.id]);
            const sub = edited ? `${direction} · 기존 ${split(origin[i.id])[0]}` : direction;
            return (
              <div key={i.id} className={`stepper-card ${edited ? "edited" : ""}`}>
                <div className="code">{i.code}</div>
                <div className="indicator-text">
                  <div className="indicator-name">{i.name}</div>
                  {sub && <div className="indicator-desc">{sub}</div>}
                </div>
                <button onClick={() => step(i.id, -1)} aria-label="낮추기">−</button>
                <div className="stepper-value">
                  <ValueInput value={simValues[i.id]} showDirection={false} onChange={(text) => setSimValues({ ...simValues, [i.id]: text })} />
                </div>
                <button onClick={() => step(i.id, 1)} aria-label="높이기">+</button>
              </div>
            );
          }),
        ])}
      </div>
      <Button onClick={() => navigate("/sim/period")}>다음</Button>
    </div>
  );
}
