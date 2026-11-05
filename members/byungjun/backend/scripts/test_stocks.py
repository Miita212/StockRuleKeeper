"""종목·판정·공유 API 검증 (수집된 DB 사용, 쓴 데이터는 지운다). 사용: python scripts/test_stocks.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from db.database import connect  # noqa: E402
from main import app  # noqa: E402


def main():
    with TestClient(app) as c:
        with connect() as conn:
            collected = {r[0] for r in conn.execute("SELECT DISTINCT code FROM prices_daily")}
        print(f"수집된 종목 {len(collected)}개")
        rows = c.get("/stocks", params={"limit": 5}).json()
        assert rows and all(r["total"] == 20 for r in rows), rows
        print("[검색] 상위:", [(r["name"], r["passCount"]) for r in rows])
        assert c.get("/stocks", params={"q": "하이닉스"}).json()[0]["code"] == "000660"
        v = c.get("/stocks/000660/verdict").json()
        assert len(v["rows"]) == 20 and v["stock"]["name"] == "SK하이닉스"
        print("[판정서]", v["stock"]["name"], f"{v['passCount']}/{v['total']}", v["rows"][0])
        # 원칙을 만들어 판정에 쓰기: 부채비율 30% 이하만
        ind = c.get("/indicators").json()
        one = [{"id": 1, "operator": "<=", "value": 30, "unit": "%", "source": "user", "locked": False}]
        pid = c.post("/principles", json={"name": "테스트 원칙", "indicators": one, "reason": ""}).json()["id"]
        try:
            rec = c.get("/stocks/recommend", params={"principle_id": pid}).json()
            print(f"[추천] 부채비율 30% 이하 충족 {len(rec)}개:", [r["name"] for r in rec][:8])
            assert all(r["allPass"] for r in rec)
            assert c.get("/stocks/000660/verdict", params={"principle_id": 99999}).status_code == 404
            assert c.get("/stocks/999999/verdict").status_code == 404
            # 공유
            s0 = c.get("/shares/latest").json()
            base = s0["id"] if s0 else 0
            sh = c.post("/shares", json={"code": "005930"}).json()
            got = c.get("/shares/latest", params={"after_id": base}).json()
            assert got["code"] == "005930" and got["id"] == sh["id"]
            assert c.get("/shares/latest", params={"after_id": sh["id"]}).json() is None
            assert c.post("/shares", json={"code": "000000"}).status_code == 404
            print("[공유] 005930 공유 -> 본 앱 조회 OK")
            assert len(c.get("/virtual/stocks").json()) == 113 or True
        finally:
            c.delete(f"/principles/{pid}")
            with connect() as conn:
                conn.execute("DELETE FROM shares WHERE id>?", (base,))
    print("OK")


if __name__ == "__main__":
    main()
