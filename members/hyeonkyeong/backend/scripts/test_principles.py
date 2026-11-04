"""원칙 API 검증. 사용 (backend 폴더에서, 임시 DB 사용):
  python scripts/test_principles.py            # fixture 모드(LLM 샘플 응답, 외부 호출 없음)
  python scripts/test_principles.py --live     # 실제 LLM으로 문장 몇 개를 변환(키 필요)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LIVE = "--live" in sys.argv
os.environ["EXTERNAL_MODE"] = "live" if LIVE else "fixture"
os.environ["DB_FILE"] = "data/test_principles.db"

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
from main import app  # noqa: E402
from services.principles import normalize  # noqa: E402


def test_normalize():
    raw = {"needs_clarification": False, "name": "테스트", "anchors": [1], "indicators": [
        {"id": 1, "operator": "<=", "value": 80},        # 정상
        {"id": 1, "operator": ">=", "value": 80},        # 방향 반대 -> 거절
        {"id": 99, "operator": "<=", "value": 1},        # 20개 밖 -> 거절
        {"id": 10, "operator": "<=", "value": 99999},    # 범위 밖 -> 거절
        {"id": 12, "operator": ">=", "value": 3}]}       # 잠긴 지표 -> 바뀌면 안 됨
    r = normalize(raw, None, locked_ids=[12])
    by = {x["id"]: x for x in r["indicators"]}
    assert by[1]["value"] == 80 and by[12]["value"] == 2 and by[12]["locked"]  # 12 기본값 2% 유지
    assert by[10]["value"] == 10 and len(r["indicators"]) == 20 and len(r["warnings"]) == 4
    # 되묻기: 값을 바꾸지 않고 선택지만 돌려준다
    c = normalize({"needs_clarification": True, "clarify": {"message": "?", "options": [
        {"label": "a", "indicator_id": 10, "operator": "<=", "value": 10}, {"label": "b", "indicator_id": 10, "operator": ">=", "value": 5}]}},
        None, [])
    assert c["needs_clarification"] and c["indicators"] == [] and len(c["clarify"]["options"]) == 1


def test_api():
    with TestClient(app) as client:
        assert client.get("/health").json()["user"] == "jangyechan"
        assert len(client.get("/indicators").json()) == 20
        r = client.post("/principles/ask", json={"text": "빚 많은 회사는 피하고 싶어"}).json()
        assert not r["needs_clarification"] and len(r["indicators"]) == 20 and r["values"]["1"] == "100% 이하"
        saved = client.post("/principles", json={"name": r["name"], "indicators": r["indicators"], "reason": r["explain_bubble"]}).json()
        pid = saved["id"]
        assert saved["version"] == 1 and client.get("/principles").json()[-1]["id"] == pid
        # 수정 -> 새 버전, 이전 버전 유지
        edited = [dict(x, value=80) if x["id"] == 1 else x for x in saved["indicators"]]
        v2 = client.put(f"/principles/{pid}", json={"name": "", "indicators": edited, "reason": "수정"}).json()
        assert v2["version"] == 2 and v2["values"]["1"] == "80% 이하"
        assert client.get(f"/principles/{pid}", params={"version": 1}).json()["values"]["1"] == "100% 이하"
        assert client.delete(f"/principles/{pid}").json()["ok"]
        assert client.get(f"/principles/{pid}").status_code == 404


def test_live():
    with TestClient(app) as client:
        cases = [("빚 많은 회사는 피하고 싶어", []), ("너무 비싼 주식은 안 살래", []), ("배당 꾸준히 주는 회사", []),
                 ("적자 기업은 제외해줘", []), ("오늘 점심 뭐 먹지", []), ("빚 적고 배당 많은 회사", [1])]
        for text, locked in cases:
            r = client.post("/principles/ask", json={"text": text, "locked_ids": locked}).json()
            if r["needs_clarification"]:
                print(f"[되묻기] {text} -> {r['clarify']['message'][:50]} / {[o['criterion'] for o in r['clarify']['options']]}")
            else:
                ch = [x for x in r["indicators"] if x["source"] != "default"]
                print(f"[변환] {text} -> {[(x['name'], x['criterion']) for x in ch]} {r['warnings']}")
        # 잠금 시나리오: 부채비율을 잠근 채로 "빚 더 엄격하게"
        base = client.post("/principles/ask", json={"text": "빚 많은 회사는 피하고 싶어"}).json()["indicators"]
        r = client.post("/principles/ask", json={"text": "빚 기준을 50%로 줄여줘", "base_indicators": base, "locked_ids": [1]}).json()
        print("[잠금] 부채비율 잠금 상태에서 50%로 수정 요청 ->", r["clarify"]["message"] if r["needs_clarification"] else r["warnings"])
        r = client.post("/principles/ask", json={"text": "배당수익률은 3% 이상으로", "base_indicators": base, "locked_ids": [1]}).json()
        by = {x["id"]: x for x in r["indicators"]}
        print("[수정] 배당수익률:", by[12]["criterion"], "/ 부채비율(잠김):", by[1]["criterion"], by[1]["locked"])


if __name__ == "__main__":
    test_normalize()
    if LIVE:
        test_live()
    else:
        test_api()
    for suffix in ("", "-journal"):
        p = config.ROOT / f"data/test_principles.db{suffix}"
        if p.exists():
            try:
                p.unlink()
            except PermissionError:
                pass
    print("OK")
