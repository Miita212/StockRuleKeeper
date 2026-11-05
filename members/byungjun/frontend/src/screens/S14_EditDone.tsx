import { useNavigate } from "react-router-dom";
import checkLarge from "../assets/icons/check-large.svg";
import Button from "../components/Button";
import { useApp } from "../store/AppContext";

export default function S14_EditDone() {
  const navigate = useNavigate();
  const { principles, editTargetId, changes } = useApp();
  const principle = principles.find((p) => p.id === editTargetId);

  return (
    <div className="screen s14">
      <div className="done-center">
        <div className="notice">
          <div className="notice-icon">
            <img src={checkLarge} width={32} height={32} alt="" />
          </div>
          <h2>원칙이 수정됐어요</h2>
          <p>{principle?.name}에 새 수치를 반영했어요.</p>
        </div>
        {changes.length > 0 && (
          <div className="change-card">
            <b>바뀐 내용</b>
            {changes.map((c) => (
              <div key={c.name} className="change-row">
                <span>{c.name}</span>
                <span>{c.before} → {c.after}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <Button onClick={() => navigate("/principles")}>원칙 리스트로 가기</Button>
    </div>
  );
}
