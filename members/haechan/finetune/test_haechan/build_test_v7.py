"""v7 시험 (haechan, 2026-11-08). 학습에는 절대 넣지 않는다.

왜: v7 보강(20개 밖 개념 거절·지표 번호 혼동·부등호 표현·되묻기 말투)이 외운 게 아니라 일반화됐는지, 학습 시작 *전에* 고정해 둔 새 문장으로 잰다.
  v5 3에폭과 v7 어댑터를 같은 문장으로 비교한다. 개념은 aug7 거절 개념과 겹치지 않게 골랐다.
구성(34건): L 20개 밖 개념 거절 10 / M 지표 번호 혼동 8 / N 부등호·방향 8 / O 되묻기 말투 8
정답은 build_test_v5.py 와 같은 방식(추출은 extract_answer, 되묻기는 사유·대상 지표만, 거절 메시지는 채점 안 함).
사용: python3 -X utf8 build_test_v7.py → test_haechan_v7.jsonl
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "data_aug"))
sys.path.insert(0, str(HERE))
from build_test_haechan import E  # noqa: E402
from gen_aug_haechan import SYSTEM, extract_answer, refusal_answer  # noqa: E402
import gen_aug_v6 as v6  # noqa: E402


def VM(iid): return ("VM", ("VALUE_MISSING", iid))
def PM(iid): return ("VM", ("PERIOD_MISSING", iid))
def AM(topic, ids): return ("AM", (topic, ids))
def RF(concept, a1, a2): return ("RF", (concept, a1, a2))


TESTS = {
    "L 20개 밖 개념 거절": [
        ("이번에 공모주 청약 받는 회사", RF("공모주 청약", "시가총액", "기간 수익률")),
        ("스톡옵션 많이 풀린 기업", RF("스톡옵션", "영업이익", "시가총액")),
        ("경영권 다툼 중인 회사는 피하고 싶어", RF("경영권 분쟁", "부채비율", "연속 영업흑자 연수")),
        ("노조 파업 걸린 적 없는 기업", RF("노조 파업", "영업이익", "매출액 증가율")),
        ("대차잔고 많이 쌓인 종목", RF("대차거래", "20일 평균 거래대금", "60일 변동성")),
        ("특허를 많이 가진 회사 찾아줘", RF("특허 보유", "영업이익", "매출액 증가율")),
        ("자회사를 따로 상장시킨 기업", RF("자회사 상장", "시가총액", "기간 수익률")),
        ("해외에 공장 많이 둔 회사", RF("해외 공장", "매출액 증가율", "영업이익")),
        ("인수합병 소문 도는 종목", RF("인수합병", "시가총액", "부채비율")),
        ("신제품 출시 앞둔 회사", RF("신제품 출시", "매출액 증가율", "영업이익")),
    ],
    "M 지표 번호 혼동": [
        ("영업이익 250억 이상이고 부채비율 90% 이하인 곳", E((5, ">=", 250), (1, "<=", 90))),
        ("시가총액 7000억 이상에 PER 11배 이하인 종목", E((14, ">=", 7000), (10, "<=", 11))),
        ("거래량이 평소의 2.5배 넘게 늘고 거래대금 25억 넘는 종목", E((20, ">", 2.5), (19, ">", 25))),
        ("영업이익 60억 이상 내는 시총 3000억 이상 회사", E((5, ">=", 60), (14, ">=", 3000))),
        ("최저점 대비 상승폭이 15% 안쪽인 주식", E((17, "<=", 15))),
        ("영업이익 증가율 20% 이상이고 영업이익 400억 이상인 기업", E((9, ">=", 20), (5, ">=", 400))),
        ("연속 배당 8년 이상에 배당수익률 3% 이상인 회사", E((13, ">=", 8), (12, ">=", 3))),
        ("하루 평균 거래대금 15억 이상이고 변동성 2.5% 이하인 종목", E((19, ">=", 15), (18, "<=", 2.5))),
    ],
    "N 부등호·방향": [
        ("PBR이 1.3배를 밑도는 종목", E((11, "<", 1.3))),
        ("자본 대비 부채가 130%를 밑도는 곳", E((1, "<", 130))),
        ("영업이익이 900억을 웃도는 기업", E((5, ">", 900))),
        ("PER 18배를 넘어서는 종목은 빼줘", E((10, "<=", 18))),
        ("시총 4000억에 못 미치는 곳은 제외해줘", E((14, ">=", 4000))),
        ("52주 저점 대비 70% 넘게 오른 종목은 빼줘", E((17, "<=", 70))),
        ("매출 성장률이 9% 안 되는 회사는 거를래", E((8, ">=", 9))),
        ("배당수익률 3%에 못 미치는 종목만 골라줘", E((12, "<", 3))),
    ],
    "O 되묻기 말투": [
        ("부채 걱정 없는 회사 찾아줘", AM("빚 부담", (1, 2, 3))),
        ("돈 잘 버는 회사만 보여줘", AM("잘 번다는 건", (5, 6, 7))),
        ("가격 매력 있는 종목 골라줘", AM("가성비", (10, 11, 16))),
        ("배당 시원시원하게 주는 회사", VM(12)),
        ("본업 수익이 넉넉한 회사 알려줘", VM(5)),
        ("매출이 빠르게 불어나는 회사 찾아줘", VM(8)),
        ("주가가 와르르 무너진 종목", PM(15)),
        ("주가가 훨훨 나는 종목 보여줘", PM(15)),
    ],
}


def main():
    answers = []
    for sp in ("train", "val"):
        for l in open(HERE.parent / "data_v6" / f"{sp}.jsonl", encoding="utf-8"):
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
            elif kind == "RF":
                ans = refusal_answer(*spec)
            else:
                ans = v6.clarify_gold(answers, *spec)
            out.append({"id": f"HT7-{n:03d}", "kind": group, "text": text, "output": json.loads(ans),
                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]})
    with open(HERE / "test_haechan_v7.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"시험 문장 {len(out)}건 → test_haechan_v7.jsonl")


if __name__ == "__main__":
    main()
