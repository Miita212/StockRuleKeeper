"""자연어→수치 변환이 '투자 관점에서 의미 있는지' 검증 (판정 기준·결과 해설은 scripts/eval_results/README.md).

사용: 서버(8000)를 원하는 모델로 켠 뒤
    python scripts/eval_meaning.py scripts/eval_results/eval_<모델이름>.json
- 문장마다 POST /principles/ask 호출, 되묻기면 가운데(보통) 선택지로 최대 2번 답한다.
- 최종 원칙으로 반도체 종목 전체를 판정해(저장 없이) 통과 종목 수·상위 종목을 기록한다. 원칙은 저장하지 않는다.
"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import connect  # noqa: E402
from services import stocks as stock_svc  # noqa: E402
from services import principles as principle_svc  # noqa: E402

OUT = sys.argv[1]

# (분류, 문장, 내가 기대하는 것)
CASES = [
    ("A", "PER 10배 이하인 회사만 볼래", "10 PER <= 10"),
    ("A", "배당수익률 3% 넘는 곳", "12 배당수익률 >= 3"),
    ("A", "부채비율 50% 이하", "1 부채비율 <= 50"),
    ("A", "PBR 1배 미만인 저평가 종목", "11 PBR < 1"),
    ("A", "시가총액 1조 이상", "14 시총 >= 1조원 (단위 함정)"),
    ("B", "빚 많은 회사는 싫어", "1 부채비율(또는 2) <=, 되묻기 수치 100~200%"),
    ("B", "싸게 사고 싶어", "10 PER/11 PBR <=, 되묻기 가능"),
    ("B", "망할 일 없는 튼튼한 회사", "1·2·3·4 건전성, 되묻기 가능"),
    ("B", "돈 잘 버는 회사", "7 순이익률 또는 5 영업이익 >="),
    ("B", "앞으로 클 회사", "8 매출 증가율/9 영업이익 증가율 >="),
    ("C", "꾸준히 돈 버는 회사", "6 연속 영업흑자 연수 >="),
    ("C", "요즘 너무 많이 오른 건 빼고 싶어", "15 기간수익률 <= 또는 17 저점 대비 <="),
    ("C", "거래 잘 되는 종목만", "19 거래대금 >="),
    ("C", "이자도 못 갚는 회사는 거르고 싶어", "3 EBITDA/금융비용 >= 1~3"),
    ("C", "배당 꾸준히 주는 회사", "13 연속 배당 연수 >="),
    ("D", "부채비율 100% 이하이고 배당수익률 2% 이상", "1 <=100, 12 >=2"),
    ("D", "PER 15배 이하, 매출 10% 이상 성장, 시총 5000억 이상", "10 <=15, 8 >=10, 14 >=0.5조"),
    ("D", "빚 적고 싸고 배당 주는 회사", "1, 10/11, 12 세 갈래"),
    ("E", "고점 대비 많이 떨어진 종목", "16 52주 고점 대비 <= (예 -30%)"),
    ("E", "주가 출렁임이 작은 종목", "18 변동성 <="),
    ("E", "덩치 큰 회사", "14 시총 >="),
    ("E", "작은 회사 위주로", "14 시총 <="),
    ("E", "갑자기 거래량 터진 종목", "20 거래량 배율 >= 2"),
    ("F", "적자 기업은 제외", "5 영업이익 > 0 또는 6 >=1"),
    ("F", "영업이익 500억 넘는 회사 찾아줘", "5 영업이익 >= 500억"),
    ("F", "자본잠식 된 곳은 빼줘", "4 자본잠식률 <= 0"),
    ("F", "최근 3개월 동안 20% 이상 오른 종목", "15 >= 20, 3개월"),
    ("G", "삼성전자 내일 오를까?", "거절"),
    ("G", "요즘 뉴스 좋은 종목 알려줘", "거절(뉴스 MVP 제외)"),
    ("G", "골든크로스 나온 종목", "거절 또는 되묻기(차트 패턴 지표 없음)"),
    ("G", "오늘 점심 뭐 먹지", "거절"),
]

# 원칙 수정 케이스: base = 부채비율 100 이하·배당 2 이상, 배당 잠금
EDIT_BASE = [{"id": 1, "operator": "<=", "value": 100, "source": "user"},
             {"id": 12, "operator": ">=", "value": 2, "source": "user"}]
EDITS = [
    ("H", "부채비율 좀 더 엄격하게 해줘", "1 <= 100보다 작게, 12 유지", []),
    ("H", "배당 기준을 4%로 올려줘", "12 잠금이라 안 바뀌어야 함", [12]),
    ("H", "PER 12배 이하도 추가해줘", "10 <=12 추가, 1·12 유지", []),
]


def user_set(indicators):
    return [x for x in indicators if x.get("source") in ("user", "inferred")]


def ask(client, text, base=None, locked=None, history=None):
    body = {"text": text, "base_indicators": base, "locked_ids": locked or [], "history": history or []}
    t = time.time()
    r = client.post("http://localhost:8000/principles/ask", json=body)
    return r.json(), round(time.time() - t, 1)


def run(client, conn, cat, text, expect, base=None, locked=None):
    steps = []
    history = []
    cur = text
    for _ in range(3):  # 되묻기는 최대 2번까지 가운데 선택지로 답한다
        res, sec = ask(client, cur, base, locked, history)
        steps.append({"text": cur, "sec": sec, "needs_clarification": res.get("needs_clarification"),
                      "clarify": res.get("clarify"), "warnings": res.get("warnings")})
        if not res.get("needs_clarification"):
            break
        opts = (res.get("clarify") or {}).get("options") or []
        if not opts:
            break
        history.append(cur)
        cur = opts[len(opts) // 2]["label"]
    out = {"cat": cat, "text": text, "expect": expect, "steps": steps}
    if not res.get("needs_clarification") and res.get("indicators"):
        core = user_set(res["indicators"])
        out["result"] = [x["criterion"] for x in core]
        out["name"] = res.get("name")
        out["explain_card"] = res.get("explain_card")
        out["explain_bubble"] = res.get("explain_bubble")
        cards = stock_svc.list_stocks(conn, res["indicators"], only_pass=True)
        out["pass_count"] = len(cards)
        out["pass_top"] = [c["name"] for c in cards[:8]]
    print(json.dumps({k: out.get(k) for k in ("cat", "text", "result", "pass_count")}, ensure_ascii=False), flush=True)
    return out


def main():
    conn = connect()
    total = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
    default_pass = len(stock_svc.list_stocks(conn, principle_svc.default_indicators(), only_pass=True))
    results = {"universe": total, "default_20_all_pass": default_pass, "cases": []}
    with httpx.Client(timeout=300) as client:
        for cat, text, expect in CASES:
            results["cases"].append(run(client, conn, cat, text, expect))
        base = [{**x, "unit": ""} for x in EDIT_BASE]
        for cat, text, expect, locked in EDITS:
            results["cases"].append(run(client, conn, cat, text, expect, base, locked))
    json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)


main()
