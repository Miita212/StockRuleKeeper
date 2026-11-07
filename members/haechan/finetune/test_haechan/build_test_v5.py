"""v5 추가 시험 (haechan, 2026-11-08). 학습에는 절대 넣지 않는다. gen_aug_v6.py 가 이 문장과 비슷한(2-gram 0.6 이상) 문장을 학습 보강에서 뺀다.

왜: v5 보강(부등호·16번 표현·끝말 추출·되묻기 기준)이 먹혔는지, 외운 게 아니라 일반화됐는지 다른 말투로 잰다.
  v4 3에폭 어댑터와 v5 어댑터를 같은 문장으로 비교한다.
구성(31건): H 부등호 10 / I 16·17 구분 5 / J 20개 안 지표 + 찾아줘류 6 / K 넓은 말·애매한 말 되묻기 10
정답은 build_test_haechan.py 와 같은 방식(추출은 extract_answer, 되묻기는 사유·대상 지표만 채점).
사용: python3 -X utf8 build_test_v5.py → test_haechan_v5.jsonl
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "data_aug"))
sys.path.insert(0, str(HERE))
from build_test_haechan import E  # noqa: E402
from gen_aug_haechan import SYSTEM, extract_answer  # noqa: E402
import gen_aug_v6 as v6  # noqa: E402


def VM(iid): return ("VM", ("VALUE_MISSING", iid))
def PM(iid): return ("VM", ("PERIOD_MISSING", iid))
def AM(topic, ids): return ("AM", (topic, ids))


TESTS = {
    "H 부등호": [
        ("영업이익 700억 넘고 부채비율 120% 미만인 기업", E((5, ">", 700), (1, "<", 120))),
        ("시가총액이 8000억 안 되는 회사", E((14, "<", 8000))),
        ("배당수익률 3.5% 초과에 PBR 1배 미만인 종목", E((12, ">", 3.5), (11, "<", 1))),
        ("매출 성장률 18% 넘는 기업만 추려줘", E((8, ">", 18))),
        ("PER이 14배를 넘지 않고 영업이익 증가율이 12% 넘는 곳", E((10, "<=", 14), (9, ">", 12))),
        ("차입금의존도 25% 미만 회사", E((2, "<", 25))),
        ("하루 거래대금 40억 넘는 종목", E((19, ">", 40))),
        ("연속 흑자 6년 넘게 이어 온 기업", E((6, ">", 6))),
        ("변동성 3.5% 넘지 않는 종목만", E((18, "<=", 3.5))),
        ("거래량이 평소의 4배 넘게 늘어난 종목", E((20, ">", 4))),
    ],
    "I 16·17 구분": [
        ("신고가에서 8% 안쪽에 있는 주식", E((16, ">=", -8))),
        ("연간 최고점 아래 12% 이내인 종목", E((16, ">=", -12))),
        ("1년 최고가에서 18%도 안 빠진 주식", E((16, ">=", -18))),
        ("52주 최저점에서 35% 이내로만 오른 종목", E((17, "<=", 35))),
        ("고점 대비 22% 넘게 하락한 종목은 빼줘", E((16, ">=", -22))),
    ],
    "J 20개 안 지표 끝말": [
        ("영업이익 800억 넘는 회사 골라줘", E((5, ">", 800))),
        ("배당수익률 4.5% 넘는 종목 알려줘", E((12, ">", 4.5))),
        ("매출순이익률 12% 넘는 곳 찾아줘", E((7, ">", 12))),
        ("PBR 0.6배가 안 되는 주식 찾아줘", E((11, "<", 0.6))),
        ("PER 9배를 넘지 않는 회사 골라줘", E((10, "<=", 9))),
        ("거래대금 70억 넘는 종목 보여줘", E((19, ">", 70))),
    ],
    "K 되묻기 기준": [
        ("빚 때문에 불안하지 않은 회사", AM("빚 부담", (1, 2, 3))),
        ("수익 탄탄한 회사 찾아줘", AM("잘 번다는 건", (5, 6, 7))),
        ("크기가 큰 상장사만 보여줘", AM("규모", (14, 19))),
        ("가격 대비 효율 좋은 종목 알려줘", AM("가성비", (10, 11, 16))),
        ("저점 대비 아직 덜 오른 종목 보여줘", VM(17)),
        ("순자산 대비 낮은 가격에 거래되는 회사", VM(11)),
        ("최근 주가가 푹 꺼진 종목", PM(15)),
        ("이익이 두둑이 남는 회사 찾아줘", VM(7)),
        ("영업이익이 쭉쭉 느는 회사 골라줘", VM(9)),
        ("배당 빵빵한 회사 알려줘", VM(12)),
    ],
}


def main():
    answers = []
    for sp in ("train", "val"):
        for l in open(HERE.parent / "data_v5" / f"{sp}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if len(r["messages"]) == 3:
                answers.append(r["messages"][2]["content"])
    out, n = [], 0
    for group, items in TESTS.items():
        for text, (kind, spec) in items:
            n += 1
            if kind == "E":
                ans = extract_answer(spec)
            elif kind == "AM":
                ans = v6.amb(*spec)
            else:
                ans = v6.clarify_gold(answers, *spec)
            out.append({"id": f"HT5-{n:03d}", "kind": group, "text": text, "output": json.loads(ans),
                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]})
    with open(HERE / "test_haechan_v5.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"시험 문장 {len(out)}건 → test_haechan_v5.jsonl")


if __name__ == "__main__":
    main()
