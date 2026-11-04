"""종목 API: 03 종목 검색(원칙 충족 개수 순), 추천, 04 판정서, 가상 주식앱 공유."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from db.database import connect
from services import stocks as svc

router = APIRouter(tags=["stocks"])


def _principle(conn, principle_id):
    try:
        return svc.resolve_principle(conn, principle_id)
    except KeyError:
        raise HTTPException(404, "원칙을 찾을 수 없어요") from None


@router.get("/stocks")
def search(principle_id: int | None = None, q: str = "", only_pass: bool = False, limit: int = 200):
    """반도체 종목 풀을 원칙 충족 개수 순으로. q는 종목명·코드 검색."""
    with connect() as conn:
        return svc.list_stocks(conn, _principle(conn, principle_id), q, only_pass, limit)


@router.get("/stocks/recommend")
def recommend(principle_id: int | None = None, limit: int = 10):
    """내 원칙을 모두 충족하는 종목(03 검색창 아래 추천). 없으면 빈 목록."""
    with connect() as conn:
        return svc.list_stocks(conn, _principle(conn, principle_id), only_pass=True, limit=limit)


@router.get("/stocks/{code}/verdict")
def verdict(code: str, principle_id: int | None = None):
    """04 판정서: 원칙의 지표별 기준·실제 값·충족 여부."""
    with connect() as conn:
        v = svc.verdict(conn, code, _principle(conn, principle_id))
    if not v:
        raise HTTPException(404, "반도체 종목 목록에 없는 종목이에요")
    return v


class ShareBody(BaseModel):
    code: str


@router.get("/virtual/stocks")
def virtual_stocks():
    """가상 주식앱의 종목 목록(이름·코드·현재가·등락률). 지표 판정은 하지 않는다."""
    with connect() as conn:
        rows = conn.execute("SELECT code, name FROM stocks ORDER BY name").fetchall()
        out = []
        for r in rows:
            last = conn.execute("SELECT close FROM prices_daily WHERE code=? ORDER BY date DESC LIMIT 1", (r["code"],)).fetchone()
            out.append({"code": r["code"], "name": r["name"], "price": last["close"] if last else None,
                        "changeRate": svc.day_change(conn, r["code"])})
        return out


@router.post("/shares")
def share(body: ShareBody):
    """가상 주식앱의 "공유하기": 종목을 본 앱으로 보낸다."""
    with connect() as conn:
        row = conn.execute("SELECT code, name FROM stocks WHERE code=?", (body.code,)).fetchone()
        if not row:
            raise HTTPException(404, "반도체 종목 목록에 없는 종목이에요")
        cur = conn.execute("INSERT INTO shares(user_id, code) VALUES (?, ?)", (config.FIXED_USER_ID, body.code))
        return {"id": cur.lastrowid, "code": row["code"], "name": row["name"]}


@router.get("/shares/latest")
def latest_share(after_id: int = 0):
    """본 앱이 몇 초마다 묻는다. after_id 이후에 공유된 종목이 있으면 가장 최근 1건, 없으면 null."""
    with connect() as conn:
        r = conn.execute("SELECT s.id, s.code, t.name FROM shares s JOIN stocks t ON t.code=s.code "
                         "WHERE s.user_id=? AND s.id>? ORDER BY s.id DESC LIMIT 1", (config.FIXED_USER_ID, after_id)).fetchone()
        return dict(r) if r else None
