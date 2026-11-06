"""보강 데이터 만들기 (haechan, 2026-11-06): 거절(S5)과 지표 혼동(S1·S2 추출).

왜: v3 3에폭 평가에서 틀린 유형
  - 거절 4건: 20개 지표 밖 개념을 지표 이름 없이 풀어 말하면("기관이 많이 사는 종목") 비슷한 지표로 되묻기를 함.
    기존 거절 데이터는 대부분 "ROE 높은 회사"처럼 지표 이름을 직접 말한 문장이다.
  - 지표 혼동: 2→4, 16→17, 17→18, 8↔9, 13→17. 두 지표 문장에서 하나를 빠뜨림 5건.

평가 공정성: 평가셋(hyeonkyeong/data/eval_*.jsonl)에서 틀린 거절 개념(현금 보유액·기관 순매수·배당 성장률·EPS 증가율)과
  평가셋에 나온 거절 개념(ROA·ROIC·PEG·MACD)은 일부러 넣지 않았다. 숫자를 지운 뒤 평가 문장과 문자 2-gram 유사도가
  0.75 이상인 문장도 뺀다. 그래서 평가 점수가 오르면 외운 게 아니라 일반화된 것이다.

출력(같은 폴더): aug_train.jsonl / aug_val.jsonl (+ *_meta.jsonl). val 은 약 10%.
사용: python3 -X utf8 gen_aug_haechan.py
"""
import glob
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEMBERS = HERE.parents[2]
SYSTEM = "너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아."
SRC = "haechan/finetune/data_aug/gen_aug_haechan.py"
rng = random.Random(20261106)

# 기본값 (학습 데이터 정답과 같음)
DEFAULTS = [
    (1, "<=", 100, "%"), (2, "<=", 30, "%"), (3, ">=", 3, "배"), (4, "<=", 0, "%"), (5, ">", 0, "억원"),
    (6, ">=", 3, "년"), (7, ">=", 5, "%"), (8, ">=", 15, "%"), (9, ">=", 10, "%"), (10, "<=", 10, "배"),
    (11, "<=", 1, "배"), (12, ">=", 2, "%"), (13, ">=", 3, "년"), (14, ">=", 10000, "억원"), (15, ">=", 10, "%"),
    (16, ">=", -20, "%"), (17, "<=", 50, "%"), (18, "<=", 2, "%"), (19, ">=", 10, "억원"), (20, ">=", 2, "배"),
]
UNIT = {i: u for i, _, _, u in DEFAULTS}


def batchim(word):
    ch = word.rstrip()[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    return ch in "0136781LMNlmn"  # 영문·숫자는 읽는 소리 기준(대략)


def eun(w): return w + ("은" if batchim(w) else "는")
def ina(w): return w + ("이나" if batchim(w) else "나")
def ro(w):
    ch = w[-1]
    return w + ("로" if not batchim(w) or ("가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 8) else "으로")
def iga(w): return w + ("이" if batchim(w) else "가")


def extract_answer(items):
    """items: [(id, op, value, period_months or None)] → 정답 JSON 문자열."""
    user = {i: (op, v, p) for i, op, v, p in items}
    out = []
    for i, op, v, u in DEFAULTS:
        if i in user:
            uop, uv, p = user[i]
            e = {"id": i, "operator": uop, "value": uv, "unit": u, "source": "user"}
            if i == 15:
                e["period_months"] = p
            out.append(e)
        else:
            out.append({"id": i, "operator": op, "value": v, "unit": u, "source": "default"})
    return json.dumps({"indicators": out, "anchors": sorted(user)}, ensure_ascii=False)


def refusal_answer(concept, alt1, alt2):
    msg = f"{eun(concept)} 아직 쓰지 않는 지표예요. {ina(alt1)} {ro(alt2)} 볼 수 있어요."
    return json.dumps({"refusal": True, "message": msg, "indicators": []}, ensure_ascii=False)


# ---------------------------------------------------------------- 거절 (20개 지표 밖 개념, 주로 이름 없이 풀어 말하기)
# (메시지에 쓸 개념 이름, 대안1, 대안2, [문장...])
REFUSE = [
    ("외국인 지분율", "시가총액", "20일 평균 거래대금", [
        "외국인이 많이 들고 있는 회사", "외국인 지분이 높은 종목만 보여줘", "외국인 보유 비중 큰 회사 위주로",
        "외국인 지분율 30% 넘는 회사", "외국 투자자 보유율 높은 주식 찾아줘"]),
    ("외국인 순매수", "20일 평균 거래대금", "거래량 증가 배율", [
        "외국인이 계속 사들이는 종목", "외국 투자자들이 몰리는 주식 보여줘", "요즘 외국인이 쓸어 담는 종목",
        "외인이 순매수 중인 주식만"]),
    ("개인 순매수", "20일 평균 거래대금", "거래량 증가 배율", [
        "개미들이 많이 사는 종목", "개인 투자자가 몰려드는 주식", "개인들이 순매수한 종목만 볼래"]),
    ("대주주 지분율", "시가총액", "부채비율", [
        "대주주가 지분을 많이 가진 회사", "최대주주 지분이 50% 넘는 기업", "오너 지분율 높은 회사가 좋아"]),
    ("내부자 매수", "기간 수익률", "52주 고점 대비", [
        "임원들이 자기 회사 주식을 사는 종목", "경영진이 주식을 사들인 회사", "사장이 직접 자사 주식 산 기업 보여줘"]),
    ("자사주 매입", "주가순자산비율", "12개월 배당수익률", [
        "자기 주식을 사들이는 회사", "자사주를 꾸준히 사는 기업 찾아줘", "주주환원으로 자기 주식 소각하는 회사"]),
    ("공매도 비율", "60일 변동성", "52주 고점 대비", [
        "공매도가 많이 몰린 종목", "공매도 세력이 붙은 주식은 빼줘", "공매도 잔고가 적은 종목만"]),
    ("신용잔고", "60일 변동성", "20일 평균 거래대금", [
        "빚내서 산 사람이 많은 종목", "신용 거래가 많이 낀 주식은 피하고 싶어", "신용 융자 비율 낮은 종목"]),
    ("배당성향", "12개월 배당수익률", "연속 배당 연수", [
        "이익 중에 배당으로 많이 돌려주는 회사", "번 돈의 절반 넘게 배당하는 기업", "순이익 대비 배당 비율 높은 곳"]),
    ("주당배당금", "12개월 배당수익률", "연속 배당 연수", [
        "한 주당 배당금이 큰 회사", "주당 배당을 1000원 넘게 주는 종목", "주당배당금 많은 기업만 골라 줘"]),
    ("분기배당", "12개월 배당수익률", "연속 배당 연수", [
        "분기마다 배당 주는 회사", "중간배당 하는 기업만 보여줘", "1년에 네 번 배당하는 종목"]),
    ("ROE", "매출순이익률", "영업이익", [
        "자기자본으로 돈을 잘 버는 회사", "주주 돈으로 이익을 많이 내는 기업", "자기자본이익률 높은 회사 찾아줘"]),
    ("매출총이익률", "매출순이익률", "영업이익", [
        "매출총이익률 40% 넘는 회사", "GPM 높은 기업 보여줘"]),
    ("재고자산 회전율", "매출액 증가율", "영업이익", [
        "재고가 빨리빨리 팔리는 회사", "재고 회전율 높은 기업", "창고에 재고가 안 쌓이는 회사가 좋아"]),
    ("수주잔고", "매출액 증가율", "영업이익 증가율", [
        "수주가 많이 쌓인 회사", "일감을 많이 따 둔 기업", "수주잔고 늘어나는 회사만"]),
    ("시장점유율", "시가총액", "매출액 증가율", [
        "업계 점유율 1등 회사", "시장을 꽉 잡고 있는 기업", "점유율이 계속 오르는 회사"]),
    ("연구개발비", "매출액 증가율", "영업이익 증가율", [
        "연구개발에 돈을 많이 쓰는 회사", "R&D 투자 많이 하는 기업", "매출 대비 연구비 비중 큰 곳"]),
    ("해외 매출 비중", "매출액 증가율", "시가총액", [
        "수출 비중이 높은 회사", "해외에서 많이 파는 기업만", "해외 매출이 절반 넘는 회사"]),
    ("업종", "시가총액", "매출액 증가율", [
        "반도체 관련주만 보여줘", "바이오 업종 종목만 볼래", "은행주 위주로 골라 줘", "2차전지 테마주 찾아줘"]),
    ("목표주가", "주가수익비율", "주가순자산비율", [
        "증권사 목표가보다 한참 싼 종목", "목표주가 괴리율 큰 주식", "애널리스트 목표가 올라간 종목"]),
    ("상한가 횟수", "기간 수익률", "거래량 증가 배율", [
        "상한가 자주 가는 종목", "요즘 상한가 친 주식만", "올해 상한가 두 번 넘게 간 종목"]),
    ("이동평균선", "기간 수익률", "52주 고점 대비", [
        "20일선 위에 있는 종목", "주가가 이평선을 뚫고 올라간 주식", "120일선 아래로 내려간 종목은 빼줘"]),
    ("ESG 점수", "부채비율", "연속 영업흑자 연수", [
        "ESG 점수 좋은 회사", "친환경 경영 잘하는 기업만", "지배구조 평가 높은 회사"]),
    ("직원 수", "시가총액", "영업이익", [
        "직원이 천 명 넘는 회사", "임직원 많은 큰 기업만"]),
    ("설립 연도", "연속 영업흑자 연수", "시가총액", [
        "세운 지 30년 넘은 회사", "업력 오래된 기업만 보여줘"]),
]
# 평가셋 개념은 넣지 않음 (위 목록에 없음을 아래에서 다시 확인)
HELD_OUT = ["현금", "기관", "배당 성장", "배당금이 늘", "EPS", "ROA", "ROIC", "PEG", "MACD", "골든크로스"]

# ---------------------------------------------------------------- 지표 혼동 (추출)
# 각 항목: (문장 틀, 지표 id, 부등호, 값 계산, 기간) — {v} 자리에 값
def P(text, iid, op, val=lambda v: v, period=None, vals=None, excl=False):
    """excl=True: '~한 건 빼줘'처럼 제외하는 말(정답은 남길 범위)."""
    return {"text": text, "id": iid, "op": op, "val": val, "period": period, "vals": vals, "excl": excl}

PCT_GROW = [5, 10, 15, 20, 25, 30, 40, 50]
YEARS = [4, 5, 6, 7, 8, 12, 15, 20]
VOL = [1, 1.5, 2, 2.5, 3, 4]
HIGH = [5, 10, 15, 20, 25, 30, 40]
LOW = [10, 20, 30, 40, 60, 100]

PHRASES = {
    8: [P("매출이 {v}% 이상 늘어난", 8, ">=", vals=PCT_GROW), P("매출 성장률이 {v}%를 넘는", 8, ">", vals=PCT_GROW),
        P("매출액이 작년보다 {v}% 이상 증가한", 8, ">=", vals=PCT_GROW), P("매출이 역성장하지 않은", 8, ">=", vals=[0])],
    9: [P("영업이익이 {v}% 이상 늘어난", 9, ">=", vals=PCT_GROW), P("본업 이익이 {v}% 넘게 증가한", 9, ">", vals=PCT_GROW),
        P("영업이익 증가율이 {v}% 이상인", 9, ">=", vals=PCT_GROW), P("영업이익이 줄지 않은", 9, ">=", vals=[0])],
    16: [P("52주 고점 대비 -{v}% 이내인", 16, ">=", lambda v: -v, vals=HIGH),
         P("최고가에서 {v}% 안쪽으로 내려온", 16, ">=", lambda v: -v, vals=HIGH),
         P("고점보다 {v}% 넘게 빠진", 16, ">=", lambda v: -v, vals=HIGH, excl=True),
         P("고점 대비 {v}% 넘게 떨어진", 16, "<", lambda v: -v, vals=HIGH)],
    17: [P("52주 저점 대비 {v}% 이내로 오른", 17, "<=", vals=LOW), P("저점에서 {v}% 이상 오른", 17, ">=", vals=LOW),
         P("바닥에서 {v}% 넘게 뛴", 17, "<=", vals=LOW, excl=True), P("52주 최저가보다 {v}% 미만으로 오른", 17, "<", vals=LOW)],
    18: [P("60일 변동성이 {v}% 이하인", 18, "<=", vals=VOL), P("주가 변동성 {v}% 미만인", 18, "<", vals=VOL),
         P("하루 출렁임이 {v}% 이내인", 18, "<=", vals=VOL)],
    13: [P("{v}년 이상 배당을 끊지 않은", 13, ">=", vals=YEARS), P("{v}년째 배당을 주고 있는", 13, ">=", vals=YEARS),
         P("배당을 {v}년 넘게 이어 온", 13, ">", vals=YEARS), P("연속 배당 {v}년 이상인", 13, ">=", vals=YEARS)],
    6: [P("{v}년 연속 흑자를 낸", 6, ">=", vals=YEARS), P("영업흑자를 {v}년 넘게 이어 온", 6, ">", vals=YEARS),
        P("{v}년 이상 적자 없이 영업이익을 낸", 6, ">=", vals=YEARS)],
    2: [P("빌린 돈이 총자산의 {v}% 이하인", 2, "<=", vals=[10, 15, 20, 25, 40]),
        P("차입금이 자산의 {v}%를 넘지 않는", 2, "<=", vals=[10, 20, 30]),
        P("차입금의존도 {v}% 미만인", 2, "<", vals=[15, 20, 30])],
    1: [P("부채가 자기자본의 {v}% 이하인", 1, "<=", vals=[50, 80, 100, 150, 200]),
        P("빚이 자본의 {v}%를 넘지 않는", 1, "<=", vals=[100, 150]), P("부채비율 {v}% 미만인", 1, "<", vals=[70, 100, 120])],
    4: [P("자본잠식률 {v}% 이하인", 4, "<=", vals=[0, 10, 20]), P("자본이 깎이지 않은", 4, "<=", vals=[0])],
    15: [P("{m}개월 수익률이 {v}% 이상인", 15, ">=", vals=[5, 10, 20, 30], period=[1, 3, 6, 12]),
         P("최근 {m}개월 동안 {v}% 넘게 오른", 15, ">", vals=[10, 20, 30], period=[1, 3, 6]),
         P("1년 수익률 {v}% 이상인", 15, ">=", vals=[10, 20, 30], period=[12])],
    20: [P("거래량이 평소보다 {v}배 넘게 터진", 20, ">", vals=[2, 3, 5]), P("평균 대비 거래량이 {v}배 이상인", 20, ">=", vals=[2, 3, 4]),
         P("거래량 증가 배율 {v}배 이상인", 20, ">=", vals=[1.5, 2, 3])],
    3: [P("EBITDA가 금융비용의 {v}배 이상인", 3, ">=", vals=[2, 3, 5, 10]),
        P("금융비용 대비 EBITDA {v}배 넘는", 3, ">", vals=[3, 5])],
    14: [P("시가총액 {v}억 이상인", 14, ">=", vals=[1000, 3000, 5000]), P("시총이 {v}조를 넘는", 14, ">", lambda v: v * 10000, vals=[1, 2, 5]),
         P("시가총액 {v}억 미만인", 14, "<", vals=[2000, 5000])],
    19: [P("하루 거래대금이 {v}억 이상인", 19, ">=", vals=[20, 30, 50, 100]),
         P("20일 평균 거래대금 {v}억 넘는", 19, ">", vals=[10, 50, 200])],
    12: [P("배당수익률 {v}% 이상인", 12, ">=", vals=[3, 4, 5])],
    10: [P("PER {v}배 이하인", 10, "<=", vals=[8, 12, 15])],
}
# 헷갈린 짝: 단일 문장 수와 함께 쓸 짝(두 지표 문장)
SINGLE = {8: 10, 9: 10, 16: 10, 17: 10, 18: 6, 13: 10, 6: 6, 2: 8, 1: 4, 4: 3, 15: 8, 20: 6, 3: 4, 14: 3, 19: 4}
PAIRS = [(8, 9, 8), (16, 18, 4), (17, 18, 4), (16, 17, 3), (13, 6, 4), (13, 12, 3), (1, 2, 5), (2, 4, 3),
         (15, 20, 4), (15, 18, 3), (14, 19, 5), (14, 20, 3), (8, 10, 3), (3, 1, 3)]
HEADS = ["회사", "종목", "기업", "주식", "곳"]
HEAD_OK = {i: ["종목", "주식"] for i in (15, 16, 17, 18, 19, 20)}
ENDS = ["", "만 보여줘", " 찾아줘", "{가} 좋아", "만 볼래요", " 위주로 골라 줘"]


def fill(p):
    v = rng.choice(p["vals"])
    m = rng.choice(p["period"]) if p["period"] else None
    t = p["text"].format(v=v, m=m)
    return t, (p["id"], p["op"], p["val"](v), m), p["excl"]


STEM = {"늘어난": "늘었", "증가한": "증가했", "오른": "올랐", "뛴": "뛰었", "터진": "터졌", "낸": "냈", "온": "왔",
        "않은": "않았", "않는": "않", "있는": "있", "넘는": "넘", "내려온": "내려왔", "떨어진": "떨어졌", "빠진": "빠졌"}
EXCL_ENDS = ["{은} 빼줘", "{은} 제외해줘", "{은} 거를래", "{은} 빼고 보여줘"]


def connect(a):
    """관형형 절 a 를 다음 절과 잇는 연결형으로: '~인' → '~이고/~이면서', '~늘어난' → '~늘었고'."""
    if a.endswith("인"):
        return a[:-1] + rng.choice(["이고 ", "이면서 "])
    for k, v in STEM.items():
        if a.endswith(k):
            return a[: -len(k)] + v + "고 "
    return a + ", "


def sentence(parts, iids):
    """parts: [(절, excl)] → 사용자 문장."""
    heads = HEADS
    for i in iids:
        if i in HEAD_OK:
            heads = HEAD_OK[i]
    head = rng.choice(heads)
    keep = [t for t, ex in parts if not ex]
    excl = [t for t, ex in parts if ex]
    if excl and not keep:  # 제외만: "고점보다 15% 넘게 빠진 종목은 빼줘"
        end = rng.choice(EXCL_ENDS).replace("{은}", "은" if batchim(head) else "는")
        return f"{excl[0]} {head}{end}"
    body = keep[0] if len(keep) == 1 else connect(keep[0]) + keep[1]
    if excl:  # "매출이 20% 이상 늘어난 종목 중에 고점보다 15% 넘게 빠진 건 빼줘"
        return f"{body} {head} 중에 {excl[0]} 건 " + rng.choice(["빼줘", "제외해줘", "빼고 보여줘"])
    end = rng.choice(ENDS).replace("{가}", "가" if not batchim(head) else "이")
    return f"{body} {head}{end}".strip()


def norm(t):
    return re.sub(r"[\d.,\s%]+", "", t)


def grams(t):
    t = norm(t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def sim(a, b):
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / max(1, len(ga | gb))


def main():
    evals = []
    for p in sorted(glob.glob(str(MEMBERS / "hyeonkyeong" / "data" / "eval_*.jsonl"))):
        evals += [json.loads(l)["text"] for l in open(p, encoding="utf-8") if l.strip()]
    assert len(evals) == 111, len(evals)
    existing = set()
    for sp in ("train", "val"):
        for l in open(HERE.parent / "data_v4" / f"{sp}.jsonl", encoding="utf-8"):
            existing.add(json.loads(l)["messages"][1]["content"].strip())

    rows, seen, dropped = [], set(), {"평가와 비슷": [], "기존과 중복": 0}

    def add(text, answer, meta):
        text = text.strip()
        if text in seen:
            return
        if text in existing:
            dropped["기존과 중복"] += 1
            return
        close = max(evals, key=lambda e: sim(text, e))
        if sim(text, close) >= 0.75:
            dropped["평가와 비슷"].append((text, close))
            return
        seen.add(text)
        rows.append(({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text},
                                   {"role": "assistant", "content": answer}]}, {**meta, "_source": SRC}))

    for concept, a1, a2, sents in REFUSE:
        assert not any(h in s or h in concept for h in HELD_OUT for s in sents), concept
        for s in sents:
            add(s, refusal_answer(concept, a1, a2), {"type": "S5", "kind": "haechan 보강: 20개 밖 개념(풀어 말하기)", "indicator_ids": [], "concept": concept})

    for iid, n in SINGLE.items():
        for _ in range(n * 3):  # 중복·필터로 빠지는 만큼 넉넉히 시도
            if sum(1 for _, m in rows if m.get("indicator_ids") == [iid]) >= n:
                break
            t, item, ex = fill(rng.choice(PHRASES[iid]))
            add(sentence([(t, ex)], [iid]), extract_answer([item]), {"type": "S1", "kind": "haechan 보강: 지표 혼동", "indicator_ids": [iid]})
    for a, b, n in PAIRS:
        for _ in range(n * 4):
            if sum(1 for _, m in rows if m.get("indicator_ids") == sorted([a, b])) >= n:
                break
            ta, ia, ea = fill(rng.choice(PHRASES[a]))
            tb, ib, eb = fill(rng.choice(PHRASES[b]))
            if ea and eb:
                continue
            add(sentence([(ta, ea), (tb, eb)], [a, b]), extract_answer([ia, ib]), {"type": "S2", "kind": "haechan 보강: 지표 혼동·두 지표", "indicator_ids": sorted([a, b])})

    rng.shuffle(rows)
    n_val = len(rows) // 10
    for name, part in (("aug_val", rows[:n_val]), ("aug_train", rows[n_val:])):
        with open(HERE / f"{name}.jsonl", "w", encoding="utf-8") as f, open(HERE / f"{name}_meta.jsonl", "w", encoding="utf-8") as g:
            for r, m in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                g.write(json.dumps(m, ensure_ascii=False) + "\n")
    kinds = {}
    for _, m in rows:
        kinds[m["type"]] = kinds.get(m["type"], 0) + 1
    print(f"만든 행 {len(rows)} (train {len(rows) - n_val} / val {n_val}), 유형 {kinds}")
    print(f"뺀 것: 기존 데이터와 같은 문장 {dropped['기존과 중복']}, 평가 문장과 비슷 {len(dropped['평가와 비슷'])}")
    for t, e in dropped["평가와 비슷"][:10]:
        print(f"   - {t}  ≈  {e}")


if __name__ == "__main__":
    main()
