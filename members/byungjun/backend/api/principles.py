"""원칙 API: 자연어 변환(ask), 저장·조회·수정(새 버전)·삭제."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.database import connect
from indicators.master import MASTER
from services import principles as svc

router = APIRouter(tags=["principles"])


class Indicator(BaseModel):
    id: int
    operator: str
    value: float
    unit: str = ""
    source: str = "default"
    locked: bool = False
    period_months: int | None = None  # 지표 15(기간 수익률)를 사용자가 기간과 함께 정했을 때만


class AskBody(BaseModel):
    text: str
    base_principle_id: int | None = None   # 저장된 원칙을 고칠 때
    base_indicators: list[Indicator] | None = None  # 아직 저장 전인 초안을 이어서 고칠 때
    locked_ids: list[int] = []
    history: list[str] = []


class SaveBody(BaseModel):
    name: str
    indicators: list[Indicator]
    reason: str = ""


def public(p: dict) -> dict:
    """화면용: 지표 문구를 붙이고, values({지표 id: 기준 문구})를 함께 준다."""
    items = svc.with_text(p["indicators"])
    return {**p, "indicators": items, "values": {str(x["id"]): x["criterion"] for x in items}}


@router.get("/indicators")
def indicators():
    return list(MASTER.values())


@router.get("/indicators/defaults")
def indicator_defaults():
    """지표 20개의 기본값(연산자·값·기준 문구). 화면에서 지표를 비활성화하면 이 값으로 되돌린다."""
    return public({"name": "기본값", "indicators": svc.default_indicators()})


@router.post("/principles/ask")
def ask(body: AskBody):
    base = [i.model_dump(exclude_none=True) for i in body.base_indicators] if body.base_indicators else None
    if body.base_principle_id is not None:
        with connect() as conn:
            saved = svc.get(conn, body.base_principle_id)
        if not saved:
            raise HTTPException(404, "원칙을 찾을 수 없어요")
        base = saved["indicators"]
    result = svc.ask(body.text, base, body.locked_ids, body.history)
    if result["indicators"]:
        result = public(result)
    return result


@router.post("/principles")
def create(body: SaveBody):
    items = [i.model_dump(exclude_none=True) for i in body.indicators]
    with connect() as conn:
        pid = svc.save(conn, body.name, items, body.reason)
        return public(svc.get(conn, pid))


@router.get("/principles")
def list_principles():
    with connect() as conn:
        return [public(p) for p in svc.list_all(conn)]


@router.get("/principles/{principle_id}")
def read(principle_id: int, version: int | None = None):
    with connect() as conn:
        p = svc.get(conn, principle_id, version)
    if not p:
        raise HTTPException(404, "원칙을 찾을 수 없어요")
    return public(p)


@router.put("/principles/{principle_id}")
def update(principle_id: int, body: SaveBody):
    """수정하면 같은 원칙에 새 버전이 쌓인다(이전 버전은 남는다)."""
    with connect() as conn:
        try:
            svc.new_version(conn, principle_id, [i.model_dump(exclude_none=True) for i in body.indicators], body.reason)
        except KeyError:
            raise HTTPException(404, "원칙을 찾을 수 없어요") from None
        if body.name:
            conn.execute("UPDATE principles SET name=? WHERE id=?", (body.name, principle_id))
        return public(svc.get(conn, principle_id))


@router.delete("/principles/{principle_id}")
def remove(principle_id: int):
    with connect() as conn:
        svc.delete(conn, principle_id)
    return {"ok": True}
