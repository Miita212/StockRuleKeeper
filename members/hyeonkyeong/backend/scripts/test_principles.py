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


def test_trained_format():
    """팀 학습 데이터 형식(로컬 Qwen3-8B 출력)을 읽는지. from_trained -> normalize."""
    from llm.principle import current_rule_text, from_trained
    from services.principles import default_indicators

    def run(raw, base=None, locked=()):
        base_map = {x["id"]: x for x in base} if base else None
        return normalize(from_trained(raw, base_map), base, list(locked))

    full = [{"id": i, "operator": op, "value": v, "unit": "", "source": "default"} for i, op, v in
            [(1, "<=", 100), (2, "<=", 30), (3, ">=", 3), (4, "<=", 0), (5, ">", 0), (6, ">=", 3), (7, ">=", 5),
             (8, ">=", 15), (9, ">=", 10), (10, "<=", 15), (11, "<=", 1), (12, ">=", 2), (13, ">=", 3),
             (14, ">=", 20000), (15, ">=", 10), (16, ">=", -20), (17, "<=", 50), (18, "<=", 2), (19, ">=", 10),
             (20, ">=", 2)]]
    full[9]["source"] = full[13]["source"] = "user"  # PER 15배, 시가총액 2만억(=2조)
    r = run({"indicators": full, "anchors": [10, 14], "explain_bubble": "설명"})
    by = {x["id"]: x for x in r["indicators"]}
    user = [x["id"] for x in r["indicators"] if x["source"] == "user"]
    assert user == [10, 14] and by[14]["value"] == 2 and by[10]["value"] == 15  # default 18개는 조건이 아님
    assert r["name"] and r["explain_bubble"] == "설명"
    # 되묻기 3종
    v = run({"needs_clarification": True, "reason": "VALUE_MISSING", "indicator_id": 1, "message": "얼마?",
             "options": [{"level": "엄격", "label": "50%", "value": 50}, {"level": "보통", "label": "100%", "value": 100}]})
    assert v["needs_clarification"] and [o["criterion"] for o in v["clarify"]["options"]] == ["50% 이하", "100% 이하"]
    a = run({"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": "어느?",
             "candidates": [{"id": 1, "label": "부채비율"}, {"id": 2, "label": "차입금의존도"}]})
    assert [o["label"] for o in a["clarify"]["options"]] == ["부채비율", "차입금의존도"] and not a["warnings"]
    p = run({"needs_clarification": True, "reason": "PERIOD_MISSING", "indicator_id": 15, "message": "기간?",
             "options": [{"label": "최근 3개월", "months": 3}, {"label": "최근 6개월", "months": 6}]})
    assert len(p["clarify"]["options"]) == 2
    # 거절
    f = run({"refusal": True, "message": "말씀드릴 수 없어요", "indicators": []})
    assert f["needs_clarification"] and f["clarify"]["message"] == "말씀드릴 수 없어요" and f["clarify"]["options"] == []
    # 수정(S4): 잠긴 시가총액은 그대로, 거래량 배율만 바뀜
    base = default_indicators()
    m = run({"changes": [{"id": 20, "name": "거래량 증가 배율", "before": 2, "after": 2.4, "unit": "배"}],
             "skipped_locked": [14]}, base, locked=[14])
    by = {x["id"]: x for x in m["indicators"]}
    assert by[20]["value"] == 2.4 and by[14]["value"] == 1 and by[14]["locked"] and any("잠긴" in w for w in m["warnings"])
    only_locked = run({"changes": [], "skipped_locked": [14]}, base, locked=[14])
    assert only_locked["needs_clarification"] and "잠겨" in only_locked["clarify"]["message"]
    # 수정 입력은 학습 형식(억원, locked:true)
    text = current_rule_text({x["id"]: x for x in base}, [14])
    assert text.startswith("현재 원칙: {") and '"id": 14, "operator": ">=", "value": 10000, "unit": "억원"' in text
    assert '"locked": true' in text
    # 양방향 지표(팀 마스터 allowed_operators): 52주 저점 대비 30% 초과는 허용, 부채비율 이상은 거절
    two = run({"indicators": [{"id": 17, "operator": ">", "value": 30, "source": "user"},
                              {"id": 1, "operator": ">=", "value": 50, "source": "user"}]})
    by = {x["id"]: x for x in two["indicators"]}
    assert by[17]["operator"] == ">" and by[1]["value"] == 100 and len(two["warnings"]) == 1
    from indicators.master import criterion_text
    assert criterion_text(17, ">", 30) == "30% 초과" and criterion_text(17, "<=", 50) == "50% 이내"


def test_replay_val():
    """팀 학습 데이터(val·train)의 정답(assistant)을 모델 출력이라고 보고 끝까지 처리되는지 확인한다."""
    import json
    folder = config.ROOT.parent.parent / "byungjun" / "finetune_merged"
    files = [folder / n for n in ("val.jsonl", "train.jsonl") if (folder / n).exists()]
    if not files:
        print("학습 데이터 없음 - 건너뜀")
        return
    from llm.principle import from_trained
    count = {}
    lines = [line for f in files for line in f.read_text(encoding="utf-8").splitlines()]
    for line in lines:
        msgs = json.loads(line)["messages"]
        if "JSON" not in msgs[0]["content"]:  # 설명용(S6·S7)은 자연어라 원칙 변환이 아니다
            continue
        base = locked = None
        first = msgs[1]["content"]
        if first.startswith("현재 원칙: "):
            rule = json.loads(first.split("\n")[0][len("현재 원칙: "):])["indicators"]
            locked = [x["id"] for x in rule if x.get("locked")]
            base = [dict(x, value=x["value"] / (10000 if x["id"] == 14 else 1), locked=x["id"] in locked) for x in rule]
        for turn in msgs[2::2]:
            raw = json.loads(turn["content"])
            r = normalize(from_trained(raw, {x["id"]: x for x in base} if base else None), base, locked or [])
            kind = "clarify" if r["needs_clarification"] else "rule"
            count[kind] = count.get(kind, 0) + 1
            if kind == "rule":
                by = {x["id"]: x for x in r["indicators"]}
                want = {x["id"]: x["value"] for x in raw.get("indicators", []) if x.get("source") == "user"}
                want |= {c["id"]: c["after"] for c in raw.get("changes", [])}
                assert len(by) == 20, raw
                for i, v in want.items():  # 사용자가 정한 값이 그대로 들어갔는지(시가총액은 억원 -> 조원)
                    assert by[i]["source"] == "user" and abs(by[i]["value"] - v / (10000 if i == 14 else 1)) < 1e-9, (raw, by[i])
                if not base:  # 새 원칙: 사용자가 정한 것 말고는 조건(source=user)이 아니어야 한다
                    assert {i for i, x in by.items() if x["source"] == "user"} == set(want), raw
                assert not [w for w in r["warnings"] if "잠긴" not in w and "기간" not in w], (raw, r["warnings"])
            elif not raw.get("refusal"):
                assert r["clarify"]["options"], raw
    print("학습 데이터 재생:", [f.name for f in files], count)


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
    test_trained_format()
    test_replay_val()
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
