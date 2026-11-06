import { useNavigate } from "react-router-dom";
import BottomSheet from "../components/BottomSheet";
import Button from "../components/Button";
import IndicatorCard from "../components/IndicatorCard";
import { categoryLabel, groupByCategory } from "../data/indicators";
import { useApp } from "../store/AppContext";
import type { Principle } from "../types";

// 06 위에 뜨는 바텀시트. principle이 null이면 닫힌 상태.
export default function S07_PrincipleDetailSheet({
  principle,
  onClose,
}: {
  principle: Principle | null;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const { setEditTargetId } = useApp();
  const groups = principle ? groupByCategory(Object.keys(principle.values).map(Number)) : [];

  function edit() {
    setEditTargetId(principle!.id);
    navigate("/principles/edit");
  }

  return (
    <BottomSheet open={principle !== null} onClose={onClose}>
      <div className="sheet-title">
        <h2>{principle?.name}</h2>
      </div>
      <div className="scroll sheet-scroll">
        {groups.map(([category, items]) => [
          <h3 key={category} className="category">{categoryLabel(category, items.length)}</h3>,
          ...items.map((i) => (
            <IndicatorCard key={i.id} indicator={i} value={principle!.values[i.id]} compact />
          )),
        ])}
      </div>
      {principle?.reason && (
        <div className="explain">
          <b>이렇게 만들었어요</b>
          <p>{principle.reason}</p>
        </div>
      )}
      <Button onClick={edit}>챗봇으로 수정하기</Button>
    </BottomSheet>
  );
}
