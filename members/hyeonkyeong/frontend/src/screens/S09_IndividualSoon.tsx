import { useNavigate } from "react-router-dom";
import searchLarge from "../assets/icons/search-large.svg";
import BottomSheet from "../components/BottomSheet";
import Button from "../components/Button";
import S10_SimSelect from "./S10_SimSelect";

// 개별 종목 시뮬레이션은 MVP 이후. "시뮬레이션" 화면 위에 안내 시트를 띄운다.
export default function S09_IndividualSoon() {
  const navigate = useNavigate();

  return (
    <>
      <S10_SimSelect />
      <BottomSheet open onClose={() => navigate("/sim")}>
        <div className="notice">
          <div className="notice-icon">
            <img src={searchLarge} width={32} height={32} alt="" />
          </div>
          <h2>개별 종목은 준비 중이에요</h2>
          <p>한 종목씩 원칙을 바꿔 보는 기능을 만들고 있어요. 지금은 원칙 전체를 바꿔 보는 시뮬레이션을 써 보세요.</p>
        </div>
        <Button onClick={() => navigate("/sim")}>원칙 커스터마이징 해 보기</Button>
      </BottomSheet>
    </>
  );
}
