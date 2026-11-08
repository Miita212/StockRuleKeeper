"""v7 보강 데이터 만들기 (haechan, 2026-11-08). v5 3에폭의 시험 실패 12건(RESULTS.md 12절)을 겨냥한다.

약점과 보강:
  ① 20개 밖 개념을 가까운 지표로 우겨 되물음(액면분할·실적 발표·절대 주가) → 거절 개념을 대폭 늘림(유상증자·공시·신용등급 등 30여 개, 말투 3~4개씩)
  ② 지표 번호 혼동(영업이익5↔시가총액14, 거래량 증가 배율20↔거래대금19, 16↔17) → 대비 문장과 두 지표 문장 늘림
  ③ 부등호/방향('안 되는·못 미치는·밑도는'=<, '웃도는·넘어서는'=>, '고점 대비 N% 넘게 하락한 건 빼줘'=>= -N) → 표현별 문장 늘림
  ④ 되묻기 경계: 넓은 말(가성비류)=고르기, 지표 하나+값 없음(배당 두둑한)=값 묻기, 기간 없는 하락=기간 묻기 → 새 말투 추가
공정성(학습 금지 세트와 개념이 겹치지 않게):
  - 시험(test_haechan·test_haechan_v5)에 나온 개념은 일부러 넣지 않는다: 액면분할, 실적 발표, 주가 절대 수준(만 원도 안 되는),
    가격 대비 효율, 크기가 큰, 푹 꺼진, 빵빵한. 공식 평가셋 개념(현금·기관·배당 성장·EPS·ROA·ROIC·PEG·MACD·골든크로스)도 제외.
  - 공식 평가셋과 문자 2-gram 유사도 0.75 이상, 시험과 0.6 이상인 문장은 뺀다.
출력: aug7_train.jsonl / aug7_val.jsonl (+ _meta). 정해진 seed라 다시 돌려도 같다.
사용: python3 -X utf8 gen_aug_v7.py
"""
import glob
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen_aug_haechan as g  # noqa: E402
import gen_aug_v6 as v6  # noqa: E402  (g.PHRASES 에 v6 표현이 합쳐진 상태로 가져옴)
from gen_aug_haechan import MEMBERS, P, SYSTEM, extract_answer, refusal_answer, sim  # noqa: E402

SRC = "haechan/finetune/data_aug/gen_aug_v7.py"
g.rng = random.Random(20261109)
rng = g.rng
g.ENDS = ["", " 찾아줘", " 찾아줘", " 보여줘", " 골라줘", " 알려줘", "만 보여줘", "{가} 좋아", "만 볼래요", " 위주로 골라 줘", " 좀 찾아줄래?"]

# 시험에 나온 개념 (학습에 넣지 않음) — 아래 문장에 이 말이 있으면 빼기
HELD_OUT = ["액면", "실적 발표", "실적발표", "원도 안", "원 이하", "원 미만", "가격 대비", "크기가", "푹 ", "꺼진", "빵빵",
            "현금", "기관", "배당 성장", "EPS", "ROA", "ROIC", "PEG", "MACD", "골든크로스"]

# ---------------------------------------------------------------- ① 거절 (개념, 대안1, 대안2, 문장들)
REFUSE = [
    ("유상증자", "시가총액", "부채비율", ["유상증자 한 번도 안 한 회사", "주주들한테 돈 걷는 증자 자주 하는 기업은 빼줘", "유상증자 공시 낸 종목", "최근에 증자한 회사 보여줘"]),
    ("무상증자", "시가총액", "기간 수익률", ["무상증자 하는 종목 찾아줘", "공짜로 주식 더 나눠주는 회사", "무증 결정한 기업만 보고 싶어"]),
    ("공시", "기간 수익률", "거래량 증가 배율", ["오늘 공시 뜬 종목", "호재성 공시 낸 회사 찾아줘", "공시가 자주 나오는 기업은 피할래"]),
    ("관리종목 지정", "연속 영업흑자 연수", "자본잠식률", ["관리종목으로 지정된 회사는 빼줘", "관리종목 위험 없는 기업만", "상장폐지 심사 받는 종목 걸러줘"]),
    ("투자경고 종목", "60일 변동성", "20일 평균 거래대금", ["투자경고 걸린 종목은 피하고 싶어", "시장경보 뜬 주식 빼고 보여줘", "투자주의 종목 아닌 것만"]),
    ("우선주", "시가총액", "12개월 배당수익률", ["우선주는 빼고 보여줘", "보통주만 골라줘", "우선주 위주로 찾아줘"]),
    ("신규 상장", "시가총액", "연속 영업흑자 연수", ["올해 새로 상장한 회사", "상장한 지 1년 안 된 종목", "IPO 한 지 얼마 안 된 기업 보여줘"]),
    ("감사의견", "연속 영업흑자 연수", "부채비율", ["감사의견 적정인 회사만", "회계 감사에서 문제 없는 기업", "감사의견 거절 받은 적 없는 종목"]),
    ("주주총회 일정", "12개월 배당수익률", "연속 배당 연수", ["이번 달 주총 하는 회사", "주주총회 앞둔 종목 보여줘", "주총 시즌에 배당 결정하는 기업"]),
    ("유통주식 수", "시가총액", "20일 평균 거래대금", ["유통되는 주식 수가 적은 종목", "시장에 풀린 물량이 작은 회사", "유통주식 비율 높은 기업 찾아줘"]),
    ("뉴스 호재", "기간 수익률", "거래량 증가 배율", ["좋은 뉴스 나온 종목", "호재 터진 회사만 보여줘", "오늘 기사 많이 나온 주식"]),
    ("소송 이력", "연속 영업흑자 연수", "부채비율", ["소송 걸린 적 없는 회사", "법적 분쟁이 없는 기업만", "재판 중인 종목은 빼줘"]),
    ("임원 보수", "영업이익", "매출순이익률", ["임원 연봉이 낮은 회사", "경영진 보수가 적은 기업", "사장 월급 과하지 않은 곳"]),
    ("직원 평균 연봉", "영업이익", "매출순이익률", ["직원 연봉 높은 회사", "평균 연봉 1억 넘는 기업", "월급 많이 주는 회사 찾아줘"]),
    ("사외이사", "부채비율", "연속 영업흑자 연수", ["사외이사 비중이 높은 회사", "이사회가 독립적인 기업만", "사외이사 많은 곳 찾아줘"]),
    ("계열사 수", "시가총액", "영업이익", ["계열사가 많은 그룹주", "자회사 많이 거느린 기업", "계열사 적은 회사만 골라줘"]),
    ("지주회사", "시가총액", "부채비율", ["지주회사만 보여줘", "지주사 말고 사업회사 위주로", "지주사 체제인 기업 찾아줘"]),
    ("신용등급", "부채비율", "차입금의존도", ["신용등급 높은 회사", "회사채 등급이 AA 이상인 기업", "신용평가 좋은 곳만 골라줘"]),
    ("공장 가동률", "매출액 증가율", "영업이익", ["공장이 풀가동되는 회사", "가동률 90% 넘는 기업", "설비를 놀리지 않는 곳 찾아줘"]),
    ("유동비율", "부채비율", "차입금의존도", ["단기에 갚을 돈보다 유동자산이 많은 회사", "유동비율 200% 넘는 기업", "당장 빚 갚을 여력이 큰 곳"]),
    ("당좌비율", "부채비율", "차입금의존도", ["당좌비율이 높은 회사", "재고 빼고도 단기 빚 갚을 수 있는 기업", "당좌자산 넉넉한 곳 보여줘"]),
    ("RSI", "기간 수익률", "52주 고점 대비", ["RSI 30 아래인 종목", "과매도 구간에 들어온 주식", "RSI가 과열권인 종목은 빼줘"]),
    ("볼린저밴드", "60일 변동성", "52주 고점 대비", ["볼린저밴드 하단에 닿은 종목", "밴드 상단을 뚫은 주식", "볼밴 아래로 내려간 종목 찾아줘"]),
    ("차트 패턴", "기간 수익률", "52주 저점 대비", ["쌍바닥 만든 종목", "헤드앤숄더 패턴 나온 주식", "삼각수렴 끝나가는 종목 찾아줘"]),
    ("배당락일", "12개월 배당수익률", "연속 배당 연수", ["배당락일이 다가오는 종목", "이번 주 배당락인 회사", "배당 기준일 임박한 기업 보여줘"]),
    ("환율 영향", "영업이익", "매출액 증가율", ["환율 오르면 이익 보는 회사", "원달러 환율에 민감한 종목", "달러 강세 수혜주 찾아줘"]),
    ("원자재 가격", "영업이익", "매출액 증가율", ["유가 오르면 좋아지는 종목", "원자재 값에 수익이 좌우되는 회사", "구리 가격 수혜 기업 보여줘"]),
    ("정책 수혜", "기간 수익률", "시가총액", ["정부 정책 덕 보는 회사", "규제 완화 수혜주", "나라에서 밀어주는 산업 종목 찾아줘"]),
    ("시장 구분", "시가총액", "20일 평균 거래대금", ["코스닥 종목만 보여줘", "코스피 상장사만 골라줘", "코넥스는 빼고 보여줘"]),
    ("애널리스트 보고서", "기간 수익률", "주가수익비율", ["증권사 리포트 많이 나온 회사", "리포트가 자주 올라오는 종목", "분석 보고서 커버하는 증권사가 많은 기업"]),
    ("이자보상배율", "EBITDA/금융비용", "부채비율", ["이자보상배율 높은 회사", "번 돈으로 이자를 몇 배나 갚는지 큰 기업", "이자 감당 여력 좋은 곳"]),
]

# ---------------------------------------------------------------- ②③ 추출 표현
LOW = [10, 20, 30, 40, 60, 100]
HIGH = [5, 10, 15, 20, 25, 30, 40]
NEWPH = {
    17: [P("1년 최저가 대비 {v}% 이하로 오른", 17, "<=", vals=LOW), P("최저가보다 {v}% 이내로만 오른", 17, "<=", vals=LOW),
         P("바닥에서 {v}% 넘게는 안 오른", 17, "<=", vals=LOW), P("52주 최저점 대비 {v}% 넘게 오른", 17, ">", vals=LOW)],
    16: [P("고점 대비 {v}% 넘게 하락한", 16, ">=", lambda v: -v, vals=HIGH, excl=True),
         P("최고가보다 {v}% 넘게 떨어진", 16, ">=", lambda v: -v, vals=HIGH, excl=True),
         P("52주 고점에서 {v}% 넘게 빠진", 16, ">=", lambda v: -v, vals=HIGH, excl=True),
         P("고점 아래로 {v}% 넘게 내려앉은", 16, ">=", lambda v: -v, vals=HIGH, excl=True),
         P("고점 대비 {v}% 넘게 하락한", 16, "<", lambda v: -v, vals=HIGH)],
    20: [P("거래량이 평소의 {v}배 넘게 늘어난", 20, ">", vals=[2, 3, 4, 5]), P("평소 거래량보다 {v}배 이상 불어난", 20, ">=", vals=[2, 3, 4]),
         P("거래량이 {v}배 넘게 폭증한", 20, ">", vals=[3, 4, 5, 10]), P("거래량 증가 배율이 {v}배를 웃도는", 20, ">", vals=[2, 3, 5])],
    19: [P("거래대금이 하루 평균 {v}억 넘는", 19, ">", vals=[10, 30, 50, 100]), P("20일 평균 거래대금 {v}억 이상 되는", 19, ">=", vals=[20, 50, 100]),
         P("하루에 {v}억 넘게 거래되는", 19, ">", vals=[20, 50, 100])],
    5: [P("영업이익이 {v}억에 못 미치는", 5, "<", vals=[50, 100, 300]), P("영업이익 {v}억 웃도는", 5, ">", vals=[100, 300, 500, 1000]),
        P("영업이익이 {v}억 이상 나오는", 5, ">=", vals=[100, 200, 500, 1000]), P("본업에서 {v}억 넘게 번", 5, ">", vals=[100, 300, 500])],
    14: [P("시총이 {v}억 안 되는", 14, "<", vals=[2000, 5000]), P("시가총액이 {v}억을 웃도는", 14, ">", vals=[1000, 3000, 5000]),
         P("시총 {v}억에 못 미치는", 14, "<", vals=[1000, 3000]), P("시가총액 {v}조 이상인", 14, ">=", lambda v: v * 10000, vals=[1, 2, 5])],
    11: [P("PBR이 {v}배에 못 미치는", 11, "<", vals=[0.7, 0.8, 1]), P("PBR {v}배 밑으로 거래되는", 11, "<", vals=[0.7, 0.8, 1]),
         P("PBR을 {v}배 웃도는", 11, ">", vals=[1, 1.5, 2])],
    10: [P("PER이 {v}배 밑인", 10, "<", vals=[8, 10, 12, 15]), P("PER {v}배에 못 미치는", 10, "<", vals=[8, 10, 12]),
         P("PER이 {v}배를 넘어서는", 10, ">", vals=[10, 15, 20])],
    1: [P("부채비율이 {v}%에 못 미치는", 1, "<", vals=[50, 80, 100, 150]), P("부채비율 {v}% 밑인", 1, "<", vals=[70, 100, 150]),
        P("부채비율이 {v}%를 웃도는", 1, ">", vals=[100, 150, 200])],
    12: [P("배당수익률이 {v}%에 못 미치는", 12, "<", vals=[2, 3, 4]), P("배당수익률 {v}%를 웃도는", 12, ">", vals=[3, 4, 5])],
    8: [P("매출 성장률이 {v}% 안 되는", 8, "<", vals=[5, 10, 15]), P("매출이 {v}% 넘게 성장한", 8, ">", vals=[10, 15, 20, 30])],
}
for k, lst in NEWPH.items():
    g.PHRASES.setdefault(k, [])
    g.PHRASES[k] = list(g.PHRASES[k]) + lst
PH = g.PHRASES
SINGLE = {17: 14, 16: 14, 20: 12, 19: 8, 5: 12, 14: 10, 11: 8, 10: 8, 1: 8, 12: 6, 8: 6}
PAIRS = [(1, 5, 14), (5, 14, 12), (14, 5, 10), (5, 8, 4), (1, 14, 6), (19, 20, 10), (20, 15, 4), (16, 17, 6), (17, 18, 4),
         (10, 5, 4), (11, 1, 4), (5, 12, 4)]

# ---------------------------------------------------------------- ④ 되묻기: (종류) → 문장. 값 묻기·기간 묻기는 학습 데이터의 같은 (사유, 지표) 정답을 가져온다.
CLARIFY = [
    (("AMB", "가성비", (10, 11, 16)), ["싸고 알찬 종목 골라줘", "값어치에 비해 저렴한 주식 찾아줘", "싸면서 탄탄한 회사 보여줘", "낸 돈보다 얻는 게 큰 종목"]),
    (("AMB", "빚 부담", (1, 2, 3)), ["빚 때문에 흔들릴 일 없는 회사", "재무적으로 무리 없는 기업만 골라줘", "빌린 돈이 부담 안 되는 회사"]),
    (("AMB", "잘 번다는 건", (5, 6, 7)), ["수익 구조가 탄탄한 회사", "장사 잘하는 기업만 보여줘", "돈 되는 사업을 하는 회사 골라줘"]),
    (("AMB", "규모", (14, 19)), ["규모가 큰 상장사만 보여줘", "규모 작은 회사는 거르고 싶어", "회사 규모를 따져서 골라줘"]),
    (("VALUE_MISSING", 12), ["배당 두둑한 회사 찾아줘", "배당 넉넉하게 주는 종목 골라줘", "배당금 풍성한 기업 보여줘", "배당 많이 챙겨주는 주식 알려줘", "배당이 후한 회사"]),
    (("VALUE_MISSING", 13), ["꾸준히 배당해 온 기업 알려줘", "해마다 빠짐없이 배당 주는 회사", "배당을 오랫동안 이어 온 종목 골라줘"]),
    (("VALUE_MISSING", 5), ["영업이익이 두둑한 회사 찾아줘", "본업 이익이 큰 기업 골라줘"]),
    (("VALUE_MISSING", 20), ["거래가 갑자기 늘어난 종목 찾아줘", "거래량이 폭발한 주식 보여줘"]),
    (("PERIOD_MISSING", 15), ["주가가 확 주저앉은 종목", "요즘 곤두박질친 주식 알려줘", "최근 주가가 크게 내려앉은 종목 찾아줘",
                             "근래 급락한 종목 보여줘", "요즘 주가가 쭉쭉 오른 종목", "최근 급등한 주식 골라줘"]),
]


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
    assert len(tests) >= 89, len(tests)
    existing, answers = set(), []
    for sp in ("train", "val"):
        for l in open(HERE.parent / "data_v6" / f"{sp}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            existing.add(r["messages"][1]["content"].strip())
            if len(r["messages"]) == 3:
                answers.append(r["messages"][2]["content"])

    rows, seen = [], set()
    drop = {"기존과 중복": 0, "시험 개념": [], "평가와 비슷": [], "시험과 비슷": []}

    def add(text, answer, meta):
        text = text.strip()
        if text in seen:
            return False
        if text in existing:
            drop["기존과 중복"] += 1
            return False
        if any(h in text for h in HELD_OUT):
            drop["시험 개념"].append(text)
            return False
        e = max(evals, key=lambda t: sim(text, t))
        if sim(text, e) >= 0.75:
            drop["평가와 비슷"].append((text, e))
            return False
        t = max(tests, key=lambda x: sim(text, x))
        if sim(text, t) >= 0.6:
            drop["시험과 비슷"].append((text, t))
            return False
        seen.add(text)
        rows.append(({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text},
                                   {"role": "assistant", "content": answer}]}, {**meta, "_source": SRC}))
        return True

    # ① 거절
    for concept, a1, a2, sents in REFUSE:
        ans = refusal_answer(concept, a1, a2)
        for s in sents:
            add(s, ans, {"type": "S5", "kind": "haechan v7 보강: 20개 밖 개념 거절", "concept": concept})

    # ②③ 추출: 새 표현 위주로 단일 지표 → 두 지표
    def count(tag, ids):
        return sum(1 for _, m in rows if m.get("tag") == tag and m.get("indicator_ids") == ids)

    for iid, n in SINGLE.items():
        newp = NEWPH[iid]
        for _ in range(n * 8):
            if count("S1", [iid]) >= n:
                break
            t, item, ex = g.fill(rng.choice(newp))
            add(g.sentence([(t, ex)], [iid]), extract_answer([item]),
                {"type": "S1", "tag": "S1", "kind": "haechan v7 보강: 부등호·번호 혼동", "indicator_ids": [iid]})
    for a, b, n in PAIRS:
        ids = sorted([a, b])
        for _ in range(n * 8):
            if count("S2", ids) >= n:
                break
            pa = rng.choice(NEWPH.get(a) or PH[a]) if rng.random() < 0.6 else rng.choice(PH[a])
            pb = rng.choice(NEWPH.get(b) or PH[b]) if rng.random() < 0.6 else rng.choice(PH[b])
            ta, ia, ea = g.fill(pa)
            tb, ib, eb = g.fill(pb)
            if ea and eb:
                continue
            add(g.sentence([(ta, ea), (tb, eb)], [a, b]), extract_answer([ia, ib]),
                {"type": "S2", "tag": "S2", "kind": "haechan v7 보강: 두 지표(번호 혼동)", "indicator_ids": ids})

    # ④ 되묻기
    for key, sents in CLARIFY:
        for s in sents:
            if key[0] == "AMB":
                ans, ids = v6.amb(key[1], key[2]), list(key[2])
            else:
                ans, ids = v6.clarify_gold(answers, key[0], key[1]), [key[1]]
            add(s, ans, {"type": "S3", "kind": f"haechan v7 보강: {key[0]} 되묻기", "indicator_ids": ids})

    rng.shuffle(rows)
    n_val = len(rows) // 10
    for name, part in (("aug7_val", rows[:n_val]), ("aug7_train", rows[n_val:])):
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
    print(f"뺀 것: 기존과 같은 문장 {drop['기존과 중복']}, 시험 개념 {len(drop['시험 개념'])}, 평가와 비슷 {len(drop['평가와 비슷'])}, 시험과 비슷 {len(drop['시험과 비슷'])}")
    for t in drop["시험 개념"]:
        print(f"   - [시험 개념] {t}")
    for t, e in drop["평가와 비슷"] + drop["시험과 비슷"]:
        print(f"   - {t}  ≈  {e}")


if __name__ == "__main__":
    main()
