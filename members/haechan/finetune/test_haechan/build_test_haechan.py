"""v3·v4 비교용 별도 시험 문장 (haechan, 2026-11-06 초안). 학습에는 절대 넣지 않는다.

왜: 공식 평가셋(111건)에는 "~찾아줘"로 끝나는 추출 문장이 없고, 풀어 말한 20개 밖 개념이 적어서
  v3 의 약점(보강 문장 233건에서 거절 18%, 추출 전체 일치 43%)이 드러나지 않았다.
  보강 데이터(data_aug)는 문장 틀로 만들었으므로 그것으로 시험하면 외운 걸 잰다 → 사람이 다른 말투로 쓴 문장이 필요하다.

구성(58건):
  A 끝말 '찾아줘·보여줘·골라줘·알려줘' 추출 12   B 풀어 말한 20개 밖 개념 거절 10 (보강 데이터에 없는 새 개념)
  C 추천·예측 거절 4                           D 헷갈리는 지표 짝, 새 표현 12
  E 지표 2~3개 6                               F 부등호 표현 6
  G 지표 안의 애매한 말 → 되묻기 8 (거절을 너무 많이 하는지 확인)

정답 JSON: 추출은 data_aug 와 같은 함수로 만든다. 되묻기는 학습 데이터에서 같은 (사유, 지표)의 정답을 그대로 가져온다
  (채점은 사유·대상 지표만 본다). 거절 메시지는 채점하지 않는다.
출력: test_haechan.jsonl (eval_model.py --data 로 바로 채점 가능한 형식)
사용: python3 -X utf8 build_test_haechan.py
"""
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "data_aug"))
from gen_aug_haechan import MEMBERS, SYSTEM, extract_answer, refusal_answer, sim  # noqa: E402

REC = "저는 종목을 추천하지 않아요. 내 원칙에 맞는지는 판정서에서 확인해 볼 수 있어요."
PRED = "저는 앞으로 오를지 내릴지는 말씀드릴 수 없어요. 원칙에 맞는 기준을 같이 정해 볼 수 있어요."
TIMING = "사고파는 시점은 알려 드리지 않아요. 내 원칙에 맞는 종목인지는 판정서에서 확인해 볼 수 있어요."


def E(*items):
    return ("E", [(i[0], i[1], i[2], i[3] if len(i) > 3 else None) for i in items])


def R(concept, a1, a2):
    return ("R", (concept, a1, a2))


def RM(msg):
    return ("RM", msg)


def C(reason, iid=None, cands=None):
    return ("C", (reason, iid, tuple(cands) if cands else None))


TESTS = {
    "A 끝말 추출": [
        ("부채비율 80% 이하인 회사 찾아줘", E((1, "<=", 80))),
        ("영업이익 500억 넘는 회사 찾아줘", E((5, ">", 500))),
        ("PBR 0.8배 이하 종목 찾아줘", E((11, "<=", 0.8))),
        ("배당수익률이 5% 넘는 주식 좀 찾아줘", E((12, ">", 5))),
        ("시총 3조 이상 대형주 찾아줘", E((14, ">=", 30000))),
        ("석 달 사이에 15% 이상 오른 종목 찾아줄래?", E((15, ">=", 15, 3))),
        ("5년 연속 영업흑자인 회사 보여줘", E((6, ">=", 5))),
        ("PER 12배 이하인 종목 보여줄래?", E((10, "<=", 12))),
        ("매출순이익률 10% 이상이고 부채비율 100% 이하인 회사 찾아줘", E((1, "<=", 100), (7, ">=", 10))),
        ("거래대금이 하루 평균 30억은 넘는 종목 찾아 주세요", E((19, ">", 30))),
        ("60일 변동성 2.5% 이하 종목 골라줘", E((18, "<=", 2.5))),
        ("연속 배당 10년 이상 기업 알려줘", E((13, ">=", 10))),
    ],
    "B 20개 밖 개념 거절": [
        ("코스닥 종목만 보여줘", R("상장 시장 구분", "시가총액", "20일 평균 거래대금")),
        ("주가가 만 원도 안 되는 주식", R("주가 수준", "주가수익비율", "주가순자산비율")),
        ("무상증자 한 회사 찾아줘", R("무상증자", "시가총액", "12개월 배당수익률")),
        ("액면분할 예정인 종목", R("액면분할", "시가총액", "거래량 증가 배율")),
        ("우선주만 골라 줘", R("우선주", "12개월 배당수익률", "시가총액")),
        ("이번 분기 실적 발표 앞둔 회사", R("실적 발표 일정", "영업이익 증가율", "매출액 증가율")),
        ("대표이사가 최근에 바뀐 회사는 빼줘", R("경영진 변경", "부채비율", "연속 영업흑자 연수")),
        ("외국계 증권사가 매수 리포트 낸 종목", R("증권사 투자의견", "주가수익비율", "주가순자산비율")),
        ("유통 주식이 적어서 품귀인 종목", R("유통 주식 수", "20일 평균 거래대금", "시가총액")),
        ("정부 정책 수혜주 찾아줘", R("테마", "시가총액", "매출액 증가율")),
    ],
    "C 추천·예측 거절": [
        ("다음 달에 오를 종목 찾아줘", RM(PRED)),
        ("부채비율 낮은 회사 중에 지금 사면 좋은 거 알려줘", RM(REC)),
        ("이 종목 지금 팔까 말까?", RM(TIMING)),
        ("PER 낮은 주식 중에 제일 괜찮은 거 하나 골라줘", RM(REC)),
    ],
    "D 지표 짝 새 표현": [
        ("52주 신고가에서 10% 이내에 있는 종목", E((16, ">=", -10))),
        ("1년 최저가 대비 25% 이하로 오른 주식", E((17, "<=", 25))),
        ("최근 60일 하루 변동폭이 2% 이하인 종목", E((18, "<=", 2))),
        ("작년 대비 매출이 12% 이상 성장한 회사", E((8, ">=", 12))),
        ("영업이익이 전년보다 25% 이상 뛴 기업", E((9, ">=", 25))),
        ("흑자를 7년 이상 계속 낸 회사", E((6, ">=", 7))),
        ("배당을 9년 연속 지급한 회사", E((13, ">=", 9))),
        ("총자산 대비 차입금이 15% 이하인 기업", E((2, "<=", 15))),
        ("자기자본 대비 부채가 90% 이하인 회사", E((1, "<=", 90))),
        ("거래량이 직전 평균의 2.5배 이상으로 늘어난 종목", E((20, ">=", 2.5))),
        ("6개월 주가 상승률 25% 이상인 종목", E((15, ">=", 25, 6))),
        ("이자비용 대비 EBITDA가 4배 이상인 회사", E((3, ">=", 4))),
    ],
    "E 지표 2~3개": [
        ("PER 10배 이하, PBR 1배 이하, 배당수익률 3% 이상인 주식 찾아줘", E((10, "<=", 10), (11, "<=", 1), (12, ">=", 3))),
        ("시총 1조 넘고 하루 거래대금 100억 넘는 종목", E((14, ">", 10000), (19, ">", 100))),
        ("부채비율 150% 이하에 영업이익 100억 이상인 회사", E((1, "<=", 150), (5, ">=", 100))),
        ("매출 성장 10% 이상, 영업이익 성장 15% 이상인 기업", E((8, ">=", 10), (9, ">=", 15))),
        ("고점 대비 15% 안쪽이고 3개월 수익률 5% 넘는 종목", E((15, ">", 5, 3), (16, ">=", -15))),
        ("연속 배당 5년 이상이고 배당수익률 4% 넘는 곳 찾아줘", E((12, ">", 4), (13, ">=", 5))),
    ],
    "F 부등호 표현": [
        ("부채비율이 200%를 넘지 않는 회사", E((1, "<=", 200))),
        ("시가총액 5000억 초과인 회사", E((14, ">", 5000))),
        ("PBR이 1배가 안 되는 종목", E((11, "<", 1))),
        ("변동성 3% 미만인 종목", E((18, "<", 3))),
        ("영업이익이 최소 200억은 되는 회사", E((5, ">=", 200))),
        ("최고점 대비 낙폭이 25% 넘는 종목은 제외해", E((16, ">=", -25))),
    ],
    "G 애매한 말 되묻기": [
        ("배당 두둑하게 주는 회사 찾아줘", C("VALUE_MISSING", 12)),
        ("몸집 큰 회사 위주로 보여줘", C("VALUE_MISSING", 14)),
        ("거래량이 확 늘어난 주식", C("VALUE_MISSING", 20)),
        ("주가가 잘 안 흔들리는 종목", C("VALUE_MISSING", 18)),
        ("몇 년째 흑자 행진 중인 회사", C("VALUE_MISSING", 6)),
        ("싸게 거래되는 주식 찾아줘", C("AMBIGUOUS_INDICATOR", cands=[10, 11])),
        ("주가가 꽤 올라온 종목", C("PERIOD_MISSING", 15)),
        ("매출이 해마다 불어나는 회사", C("VALUE_MISSING", 8)),
    ],
}


def main():
    train = []
    for sp in ("train", "val"):
        for l in open(HERE.parent / "data_v4" / f"{sp}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if len(r["messages"]) == 3:
                train.append((r["messages"][1]["content"], r["messages"][2]["content"]))
    aug = []
    for sp in ("aug_train", "aug_val"):
        aug += [json.loads(l)["messages"][1]["content"] for l in open(HERE.parent / "data_aug" / f"{sp}.jsonl", encoding="utf-8")]
    evals = []
    for p in sorted(glob.glob(str(MEMBERS / "hyeonkyeong" / "data" / "eval_*.jsonl"))):
        evals += [json.loads(l)["text"] for l in open(p, encoding="utf-8") if l.strip()]

    def clarify_gold(reason, iid, cands):
        for _, a in train:
            try:
                d = json.loads(a)
            except Exception:
                continue
            if not d.get("needs_clarification") or d.get("reason") != reason:
                continue
            if cands:
                if sorted(c["id"] for c in d.get("candidates", [])) == sorted(cands):
                    return a
            elif d.get("indicator_id") == iid:
                return a
        raise SystemExit(f"학습 데이터에 ({reason}, {iid or cands}) 되묻기 정답이 없음")

    out, warn = [], []
    n = 0
    for group, items in TESTS.items():
        for text, (kind, spec) in items:
            n += 1
            if kind == "E":
                ans = extract_answer(spec)
            elif kind == "R":
                ans = refusal_answer(*spec)
            elif kind == "RM":
                ans = json.dumps({"refusal": True, "message": spec, "indicators": []}, ensure_ascii=False)
            else:
                ans = clarify_gold(*spec)
            # 겹침 점검
            for name, pool in (("학습", [t for t, _ in train]), ("보강", aug), ("평가", evals)):
                if text in pool:
                    warn.append(f"{text}: {name} 데이터에 같은 문장")
                best = max(pool, key=lambda t: sim(text, t))
                if sim(text, best) >= 0.6:
                    warn.append(f"{text}: {name}와 비슷({sim(text, best):.2f}) ≈ {best}")
            out.append({"id": f"HT-{n:03d}", "kind": group, "text": text, "output": json.loads(ans),
                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]})
    with open(HERE / "test_haechan.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"시험 문장 {len(out)}건 → test_haechan.jsonl")
    for w in warn:
        print("  [확인]", w)


if __name__ == "__main__":
    main()
