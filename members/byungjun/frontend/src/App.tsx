import { Navigate, Route, Routes } from "react-router-dom";
import "./App.css";
import AppLayout from "./layouts/AppLayout";
import PrincipleChat from "./screens/PrincipleChat";
import S04_Verdict from "./screens/S04_Verdict";
import S03_StockSearch from "./screens/S03_StockSearch";
import S06_PrincipleList from "./screens/S06_PrincipleList";
import S09_IndividualSoon from "./screens/S09_IndividualSoon";
import S10_SimSelect from "./screens/S10_SimSelect";
import S11_SimAdjust from "./screens/S11_SimAdjust";
import S12_SimPeriod from "./screens/S12_SimPeriod";
import S13_SimReport from "./screens/S13_SimReport";
import S14_EditDone from "./screens/S14_EditDone";
import Settings from "./screens/Settings";

// 화면 흐름 연결은 이 파일 한 곳에서 한다. 하단 바는 AppLayout이 정한다.
// 원칙 만들기(01·02-1·02)와 고치기(08·02-2)는 대화가 이어지는 PrincipleChat 한 화면이다.
function App() {
  return (
    <div className="app">
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<PrincipleChat />} />
          <Route path="/clarify" element={<Navigate to="/" replace />} />
          <Route path="/setup" element={<Navigate to="/" replace />} />
          <Route path="/setup-edit" element={<Navigate to="/principles/edit" replace />} />
          <Route path="/stocks" element={<S03_StockSearch />} />
          <Route path="/stocks/:code" element={<S04_Verdict />} />
          <Route path="/principles" element={<S06_PrincipleList />} />
          <Route path="/principles/edit" element={<PrincipleChat edit />} />
          <Route path="/edit-done" element={<S14_EditDone />} />
          <Route path="/sim-menu" element={<S10_SimSelect />} />
          <Route path="/settings" element={<Settings />} />

          <Route path="/sim" element={<S10_SimSelect />} />
          <Route path="/sim/individual" element={<S09_IndividualSoon />} />
          <Route path="/sim/adjust" element={<S11_SimAdjust />} />
          <Route path="/sim/period" element={<S12_SimPeriod />} />
          <Route path="/sim/report" element={<S13_SimReport />} />
        </Route>
      </Routes>
    </div>
  );
}

export default App;
