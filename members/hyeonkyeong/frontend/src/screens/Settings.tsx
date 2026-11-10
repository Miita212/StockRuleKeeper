import { useState } from "react";
import Chip from "../components/Chip";
import { getAdmin, getHome, HOME_OPTIONS, setAdmin, setHome } from "../data/home";

// 설정: 관리자 모드를 켜면 앱을 켰을 때 처음 보이는 화면(초기화면)을 고를 수 있다.
export default function Settings() {
  const [admin, setAdminState] = useState(getAdmin());
  const [home, setHomeState] = useState(getHome());

  function toggleAdmin() {
    setAdmin(!admin);
    setAdminState(!admin);
  }

  function pickHome(to: string) {
    setHome(to);
    setHomeState(to);
  }

  return (
    <div className="screen">
      <h1 className="title">설정</h1>
      <div className="admin-box">
        <label className="switch-box admin-head">
          관리자 모드
          <button
            type="button"
            role="switch"
            aria-checked={admin}
            className={`switch${admin ? " on" : ""}`}
            onClick={toggleAdmin}
          />
        </label>
        {admin && (
          <>
            <p className="label">초기화면</p>
            <p className="note">앱을 켰을 때 가장 먼저 보이는 화면이에요. 원칙이 하나도 없으면 항상 원칙 생성이 먼저 나와요.</p>
            <div className="chip-row">
              {HOME_OPTIONS.map((o) => (
                <Chip key={o.to} selected={home === o.to} onClick={() => pickHome(o.to)}>{o.label}</Chip>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
