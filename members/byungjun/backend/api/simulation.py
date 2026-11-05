"""시뮬레이션 API(11~13 화면): 원칙 A의 수치를 고친 B를 만들어 수정 전/후를 비교하고 종합 리포트를 돌려준다."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.database import connect
from indicators.master import MASTER
from llm.report import write_report
from services import principles as principle_svc
from services import simulation as sim_svc

router = APIRouter(tags=["simulation"])


class Change(BaseModel):
    id: int
    operator: str
    value: float


class SimBody(BaseModel):
    principle_id: int                 # 원칙 A (저장된 원칙)
    changes: list[Change] = []        # A에서 고친 지표들 -> 수정 후 B
    months: int = 3                   # 3, 6, 12
    locked_ids: list[int] = []        # 잠근 지표(리포트에 "바뀌지 않았다"고 한 줄 언급)
    with_report: bool = True          # False면 숫자표만(빠른 응답)


@router.post("/simulation")
def simulate(body: SimBody):
    if body.months not in (3, 6, 12):
        raise HTTPException(400, "기간은 3, 6, 12개월 중에서 골라 주세요")
    with connect() as conn:
        p = principle_svc.get(conn, body.principle_id)
        if not p:
            raise HTTPException(404, "원칙을 찾을 수 없어요")
        result = sim_svc.run(conn, p["indicators"], [c.model_dump() | {"source": "user"} for c in body.changes], body.months)
    out = {"principle": {"id": p["id"], "name": p["name"]}, "result": result}
    if body.with_report:
        locked = [MASTER[i]["name"] for i in body.locked_ids if i in MASTER]
        report, source = write_report(result, p["name"], locked)
        out.update(report=report, report_source=source)
    return out
