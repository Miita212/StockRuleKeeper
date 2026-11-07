"""v5 보강 데이터 만들기 (haechan, 2026-11-08). v4 3에폭의 남은 약점을 겨냥한다.

약점(RESULTS.md 11절)과 보강:
  ① 부등호: '넘는·초과(>)', '안 되는·미만(<)', '넘지 않는(<=)'을 이상·이하로 읽음 → 한 지표·두 지표 문장에 섞어 넣음
  ② 16번 '신고가/최고점에서 N% 이내'를 17번으로 읽음 → 고점 쪽 표현을 다양하게
  ③ 20개 안 지표(영업이익·배당수익률·순이익률·PBR 등) 문장이 '찾아줘/골라줘'로 끝나면 거절함 → 끝말 추출·되묻기 예시
  ④ 되묻기: 넓은 말(빚 부담·벌이·규모·가성비)은 '고르기', 지표 하나로 읽히는 말(저점 대비 덜 오른, 자산 대비 싼, 마진)은 '값 묻기',
     기간 없는 하락/상승은 '기간 묻기'  (LABEL_AUDIT.md 1절)
공정성: 공식 평가셋 문장과 2-gram 유사도 0.75 이상, 시험(test_haechan·test_haechan_v5)과 0.6 이상인 문장은 뺀다.
  '가성비'는 공식 평가셋에도 나온 개념이라 평가 점수 일부는 개념 보강 효과가 섞인다(시험 v5에는 다른 표현으로 따로 잰다).
출력: aug6_train.jsonl / aug6_val.jsonl (+ _meta). 정해진 seed라 다시 돌려도 같다.
사용: python3 -X utf8 gen_aug_v6.py
"""
import glob
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_aug_haechan as g  # noqa: E402
from gen_aug_haechan import MEMBERS, P, SYSTEM, extract_answer, sim, eun  # noqa: E402

SRC = "haechan/finetune/data_aug/gen_aug_v6.py"
g.rng = random.Random(20261108)  # fill()·sentence()가 이 모듈의 rng 를 쓴다
rng = g.rng

# 끝말: 찾아줘·골라줘 쪽을 늘림
g.ENDS = ["", " 찾아줘", " 찾아줘", " 보여줘", " 골라줘", " 알려줘", "만 보여줘", "{가} 좋아", "만 볼래요", " 위주로 골라 줘", " 좀 찾아줄래?"]

NEW = {
    16: [P("신고가에서 {v}% 이내인", 16, ">=", lambda v: -v, vals=[5, 10, 15, 20]),
         P("연중 최고점 대비 {v}% 안에 있는", 16, ">=", lambda v: -v, vals=[5, 10, 15, 20, 25]),
         P("최고점에서 {v}% 이내로만 내려온", 16, ">=", lambda v: -v, vals=[5, 10, 15, 20]),
         P("1년 내 최고가보다 {v}% 이상은 안 빠진", 16, ">=", lambda v: -v, vals=[10, 15, 20, 30]),
         P("52주 최고가 대비 {v}% 넘게 하락한", 16, "<", lambda v: -v, vals=[20, 30, 40])],
    5: [P("영업이익이 {v}억 넘는", 5, ">", vals=[100, 300, 500, 1000, 2000]), P("영업이익 {v}억을 초과하는", 5, ">", vals=[100, 300, 500, 1000]),
        P("영업이익을 {v}억 이상 내는", 5, ">=", vals=[100, 300, 500, 1000]), P("영업이익이 {v}억 안 되는", 5, "<", vals=[50, 100, 300])],
    12: [P("배당수익률이 {v}% 넘는", 12, ">", vals=[2, 3, 4, 5, 6]), P("배당을 시가의 {v}% 넘게 주는", 12, ">", vals=[3, 4, 5])],
    7: [P("매출순이익률이 {v}% 넘는", 7, ">", vals=[3, 5, 8, 10, 15]), P("순이익률이 {v}%는 되는", 7, ">=", vals=[3, 5, 8, 10]),
        P("매출 대비 순이익이 {v}%를 넘는", 7, ">", vals=[5, 10, 15])],
    11: [P("PBR이 {v}배가 안 되는", 11, "<", vals=[0.7, 0.8, 1, 1.2]), P("PBR {v}배 미만인", 11, "<", vals=[0.7, 0.8, 1, 1.5]),
         P("PBR을 {v}배 넘지 않는", 11, "<=", vals=[0.8, 1, 1.2, 1.5])],
    10: [P("PER이 {v}배 안 되는", 10, "<", vals=[8, 10, 12, 15]), P("PER {v}배를 넘지 않는", 10, "<=", vals=[8, 10, 12, 15, 20])],
    18: [P("60일 변동성이 {v}%를 넘지 않는", 18, "<=", vals=[1.5, 2, 2.5, 3]), P("변동성이 {v}% 안 되는", 18, "<", vals=[1.5, 2, 3])],
}
PH = {}
for k, v in g.PHRASES.items():
    PH[k] = list(v)
for k, v in NEW.items():
    PH.setdefault(k, [])
    PH[k] += v
g.PHRASES = PH
SINGLE = {5: 14, 12: 12, 7: 10, 11: 12, 10: 8, 16: 18, 18: 6, 14: 8, 19: 8, 8: 6, 9: 6, 1: 6, 2: 4, 13: 4, 6: 4, 15: 6}
PAIRS = [(14, 19, 8), (5, 1, 8), (8, 9, 6), (12, 13, 6), (16, 15, 6), (10, 11, 6), (5, 7, 6), (14, 5, 6), (1, 6, 4), (11, 12, 4),
         (7, 12, 3), (16, 18, 3)]

# ---- 되묻기 --------------------------------------------------------------------
NAME = {1: "부채비율", 2: "차입금의존도", 3: "EBITDA/금융비용", 5: "영업이익", 6: "연속 영업흑자 연수", 7: "매출순이익률",
        10: "PER", 11: "PBR", 14: "시가총액", 19: "20일 평균 거래대금", 16: "52주 고점 대비"}


def amb(topic, ids):
    msg = f"{eun(topic)} 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?"
    return json.dumps({"needs_clarification": True, "reason": "AMBIGUOUS_INDICATOR", "message": msg,
                       "candidates": [{"id": i, "name": NAME[i]} for i in ids]}, ensure_ascii=False)


# (reason, 지표 또는 후보) → 문장들. 값 묻기·기간 묻기는 학습 데이터의 같은 (사유, 지표) 정답을 가져온다.
CLARIFY = [
    (("AMB", "빚 부담", (1, 2, 3)), ["빚 부담 없는 회사 위주로 보고 싶어", "빚 때문에 속 썩일 일 없는 회사", "재무 부담 적은 회사 찾아줘",
                                   "빚 압박 없는 기업만 골라줘", "빚 걱정이 덜한 회사 좋아요", "갚을 빚이 가벼운 회사"]),
    (("AMB", "잘 번다는 건", (5, 6, 7)), ["벌이가 좋은 회사 찾아줘", "돈 잘 긁어모으는 기업 위주로", "수입이 쏠쏠한 회사가 좋아", "수익이 짭짤한 기업 골라줘",
                                    "벌이 괜찮은 회사만 추려 줘"]),
    (("AMB", "규모", (14, 19)), ["규모 있는 기업만 보고 싶어요", "규모가 어느 정도 되는 회사 찾아줘", "규모가 큰 기업 위주로 골라줘"]),
    (("AMB", "가성비", (10, 11, 16)), ["가성비 갑인 종목 골라줘", "가성비 따지는 투자를 하고 싶어", "가성비 괜찮은 회사 보여줘"]),
    (("VALUE_MISSING", 17), ["저점에서 별로 안 오른 주식", "바닥 대비 덜 오른 종목 찾아줘", "저점 대비 상승폭이 작은 종목", "최저가에서 아직 많이 안 뛴 주식 골라줘",
                            "1년 최저가보다 크게 안 오른 종목"]),
    (("VALUE_MISSING", 11), ["자산 가치에 비해 싼 회사", "장부상 순자산보다 싸게 거래되는 종목", "순자산 대비 가격이 낮은 회사 찾아줘", "가진 자산에 비해 주가가 저렴한 종목"]),
    (("VALUE_MISSING", 7), ["마진 좋은 회사가 좋아요", "팔 때마다 이익이 두둑이 남는 회사", "남는 게 많은 장사를 하는 기업 찾아줘"]),
    (("PERIOD_MISSING", 15), ["요즘 많이 빠진 종목", "최근 주가가 크게 떨어진 종목", "근래 주가가 꺾인 종목 찾아줘", "얼마 전부터 주가가 내려앉은 종목", "최근 주가가 쑥 오른 종목 찾아줘",
                             "요새 급하게 오른 주식 골라줘"]),
    (("VALUE_MISSING", 12), ["배당 짭짤한 회사 찾아줘", "배당 후하게 주는 주식 골라줘"]),
    (("VALUE_MISSING", 14), ["시총 큰 회사 위주로 찾아줘", "대형주 위주로 골라줘"]),
    (("VALUE_MISSING", 5), ["영업이익 많이 내는 회사 찾아줘", "본업으로 크게 버는 회사 골라줘"]),
    (("VALUE_MISSING", 8), ["매출 빠르게 느는 회사 찾아줘", "매출이 쑥쑥 오르는 곳 골라줘"]),
    (("VALUE_MISSING", 20), ["거래량 확 터진 종목 찾아줘", "거래가 갑자기 몰리는 주식 골라줘"]),
    (("VALUE_MISSING", 6), ["흑자를 계속 내는 회사 찾아줘", "적자 없이 버텨 온 회사 골라줘"]),
    (("VALUE_MISSING", 13), ["배당을 오래 준 회사 찾아줘", "배당 끊긴 적 없는 기업 골라줘"]),
]


def clarify_gold(train, reason, iid):
    for a in train:
        try:
            d = json.loads(a)
        except Exception:
            continue
        if isinstance(d, dict) and d.get("needs_clarification") and d.get("reason") == reason and d.get("indicator_id") == iid:
            return a
    raise SystemExit(f"학습 데이터에 ({reason}, {iid}) 되묻기 정답이 없음")


def main():
    def texts(pattern):
        out = []
        for p in sorted(glob.glob(pattern)):
            for l in open(p, encoding="utf-8"):
                if l.strip():
                    d = json.loads(l)
                    out.append(d.get("text") or d["messages"][1]["content"])
        return out

    evals = texts(str(MEMBERS / "hyeonkyeong" / "data" / "eval_*.jsonl"))
    assert len(evals) == 111
    tests = texts(str(HERE.parent / "test_haechan" / "test_haechan*.jsonl"))
    existing, answers = set(), []
    for sp in ("train", "val"):
        for l in open(HERE.parent / "data_v5" / f"{sp}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            existing.add(r["messages"][1]["content"].strip())
            if len(r["messages"]) == 3:
                answers.append(r["messages"][2]["content"])

    rows, seen = [], set()
    drop = {"기존과 중복": 0, "평가와 비슷": [], "시험과 비슷": []}

    def add(text, answer, meta):
        text = text.strip()
        if text in seen:
            return
        if text in existing:
            drop["기존과 중복"] += 1
            return
        e = max(evals, key=lambda t: sim(text, t))
        if sim(text, e) >= 0.75:
            drop["평가와 비슷"].append((text, e))
            return
        t = max(tests, key=lambda x: sim(text, x))
        if sim(text, t) >= 0.6:
            drop["시험과 비슷"].append((text, t))
            return
        seen.add(text)
        rows.append(({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text},
                                   {"role": "assistant", "content": answer}]}, {**meta, "_source": SRC}))

    for iid, n in SINGLE.items():
        for _ in range(n * 4):
            if sum(1 for _, m in rows if m.get("indicator_ids") == [iid] and m["type"] == "S1") >= n:
                break
            t, item, ex = g.fill(rng.choice(PH[iid]))
            add(g.sentence([(t, ex)], [iid]), extract_answer([item]), {"type": "S1", "kind": "haechan v6 보강: 부등호·끝말", "indicator_ids": [iid]})
    for a, b, n in PAIRS:
        for _ in range(n * 5):
            if sum(1 for _, m in rows if m.get("indicator_ids") == sorted([a, b]) and m["type"] == "S2") >= n:
                break
            ta, ia, ea = g.fill(rng.choice(PH[a]))
            tb, ib, eb = g.fill(rng.choice(PH[b]))
            if ea and eb:
                continue
            add(g.sentence([(ta, ea), (tb, eb)], [a, b]), extract_answer([ia, ib]), {"type": "S2", "kind": "haechan v6 보강: 부등호·두 지표", "indicator_ids": sorted([a, b])})
    for key, sents in CLARIFY:
        for s in sents:
            if key[0] == "AMB":
                ans, ids = amb(key[1], key[2]), list(key[2])
            else:
                ans, ids = clarify_gold(answers, key[0], key[1]), [key[1]]
            add(s, ans, {"type": "S3", "kind": f"haechan v6 보강: {key[0]} 되묻기", "indicator_ids": ids})

    rng.shuffle(rows)
    n_val = len(rows) // 10
    for name, part in (("aug6_val", rows[:n_val]), ("aug6_train", rows[n_val:])):
        with open(HERE / f"{name}.jsonl", "w", encoding="utf-8") as f, open(HERE / f"{name}_meta.jsonl", "w", encoding="utf-8") as h:
            for r, m in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                h.write(json.dumps(m, ensure_ascii=False) + "\n")
    kinds = {}
    for _, m in rows:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    print(f"만든 행 {len(rows)} (train {len(rows) - n_val} / val {n_val})")
    for k, v in sorted(kinds.items()):
        print(f"  {v:4d} {k}")
    print(f"뺀 것: 기존과 같은 문장 {drop['기존과 중복']}, 평가와 비슷 {len(drop['평가와 비슷'])}, 시험과 비슷 {len(drop['시험과 비슷'])}")
    for t, e in drop["평가와 비슷"] + drop["시험과 비슷"]:
        print(f"   - {t}  ≈  {e}")


if __name__ == "__main__":
    main()
