"""dev셋(모델 비교용 정답 문제집)을 만들어 dev_set.jsonl로 저장한다.

실행: python members/haechan/data/build_dev.py   (먼저 build_pilot.py를 실행해 pilot_labels.jsonl이 있어야 함)

구성
 - pilot : 시범 라벨 33개 (질문 리스트에서 뽑은 것)
 - new   : 직접 쓴 문제 (은어, 모호, 미지원 지표, 설명/관리/점검, 범위 밖). 질문 리스트에 없는 문장
 - typo  : pilot/new 중 일부의 오타 변형. 정답은 원본과 같다.

group: 같은 취지의 문장 묶음. 오타 변형은 원본과 같은 group이다.
       학습셋을 만들 때 dev의 group과 겹치는 질문(질문 리스트의 pilot 33개 포함)은 제외해야 한다.

라벨 규칙은 build_pilot.py 위쪽의 R1~R7을 따른다. 단위는 indicators.py의 잠정 단위.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from build_pilot import L, c  # noqa: E402
from llm.schema import validate  # noqa: E402

SEED = 20261104

# (카테고리, 질문, 라벨, note)
NEW = [
    # --- 수치가 명확: 조건 확정 (R1) ---
    ("수치", "PBR 1배 미만 종목만 보고 싶어", L(conds=[c("PBR", "<", 1)]), "R1"),
    ("수치", "시총 5천억 넘는 곳", L(conds=[c("MARKET_CAP", ">", 5000)]), "R1 5천억원 = 5,000억원"),
    ("수치", "영업이익 증가율 20% 이상인 회사", L(conds=[c("OPERATING_PROFIT_GROWTH", ">=", 20)]), "R1"),
    ("수치", "10년 연속 배당 준 회사", L(conds=[c("CONSECUTIVE_DIVIDEND_YEARS", ">=", 10)]), "R1"),
    ("수치", "최근 3개월 수익률 10% 넘는 종목", L(conds=[c("PERIOD_RETURN", ">", 10, 3)]), "R1 기간 3개월"),
    ("수치", "52주 최고가에서 30% 넘게 빠진 건 제외해줘", L(conds=[c("FROM_52W_HIGH", ">=", -30)]), "R1"),
    ("수치", "최근 20일 평균 거래대금 50억 이상", L(conds=[c("AVG_TRADING_VALUE_20D", ">=", 50)]), "R1"),
    ("수치", "거래량이 평소의 3배 이상 터진 종목", L(conds=[c("VOLUME_SURGE_RATIO", ">=", 3)]), "R1"),
    ("수치", "매출액 증가율 10% 이상이고 PBR 2 이하", L(conds=[c("REVENUE_GROWTH", ">=", 10), c("PBR", "<=", 2)]), "R1 복수 조건"),
    ("수치", "차입금의존도 30% 이하인 회사", L(conds=[c("BORROWING_DEPENDENCY", "<=", 30)]), "R1"),
    ("수치", "EBITDA가 금융비용의 5배 이상인 곳", L(conds=[c("EBITDA_INTEREST_COVER", ">=", 5)]), "R1"),
    ("수치", "매출순이익률 10% 이상인 회사", L(conds=[c("NET_MARGIN", ">=", 10)]), "R1"),
    ("수치", "5년 연속 영업이익 흑자인 곳", L(conds=[c("CONSECUTIVE_PROFIT_YEARS", ">=", 5)]), "R1"),
    ("수치", "영업이익 1000억 넘는 회사", L(conds=[c("OPERATING_PROFIT", ">", 1000)]), "R1"),
    ("수치", "배당수익률 4% 넘고 부채비율 150% 이하", L(conds=[c("DIVIDEND_YIELD_12M", ">", 4), c("DEBT_RATIO", "<=", 150)]), "R1 복수 조건"),
    ("수치", "52주 저점 대비 50% 이상 오른 종목", L(conds=[c("FROM_52W_LOW", ">=", 50)]), "R1"),
    ("수치", "최근 60거래일 변동성 25% 이하", L(conds=[c("VOLATILITY_60D", "<=", 25)]), "R1"),
    ("수치", "PER 12 이하에 시총 1조 이상", L(conds=[c("PER", "<=", 12), c("MARKET_CAP", ">=", 10000)]), "R1 1조원 = 10,000억원"),
    # --- 은어·모호: 되묻기 (R2) ---
    ("은어", "야르한 종목 알려줘",
     L(q="성장률이 높은 종목을 원하시나요? 어떤 기준으로 볼까요?",
       choices=["매출액 증가율 10% 이상", "영업이익 증가율 20% 이상"]),
     "R2 요구사항 문서의 은어 예시(야르한 -> 성장률)"),
    ("은어", "존버할 만한 튼튼한 회사",
     L(q="'튼튼하다'를 어떤 기준으로 볼까요?",
       choices=["부채비율 100% 이하", "5년 연속 영업이익 흑자", "부채비율 100% 이하 + 5년 연속 영업이익 흑자"]), "R2"),
    ("은어", "급등주 따라가고 싶어",
     L(q="'급등'을 어떤 기준으로 볼까요?",
       choices=["최근 3개월 수익률 20% 이상", "거래량 증가 배율 3배 이상"]), "R2"),
    ("은어", "대장주만 담고 싶다",
     L(q="'대장주'를 시가총액 얼마 이상으로 볼까요?",
       choices=["시가총액 1조원 이상", "시가총액 5조원 이상"]), "R2"),
    ("은어", "돈 잘 버는 알짜 기업만",
     L(q="'돈 잘 번다'를 어떤 기준으로 볼까요?",
       choices=["매출순이익률 10% 이상", "영업이익 1,000억원 이상"]), "R2"),
    ("은어", "배당 따박따박 주는 곳",
     L(q="'따박따박'을 어떤 기준으로 볼까요?",
       choices=["연속 현금배당 5년 이상", "연속 현금배당 10년 이상 + 배당수익률 3% 이상"]), "R2"),
    ("은어", "거품 낀 주식은 피하고 싶어",
     L(q="'거품'을 어떤 기준으로 볼까요?",
       choices=["PER 20배 이하", "PBR 3배 이하"]), "R2"),
    ("은어", "개미들 몰리는 종목",
     L(q="'몰린다'를 어떤 기준으로 볼까요?",
       choices=["거래량 증가 배율 3배 이상", "최근 20거래일 평균 거래대금 100억원 이상"]), "R2"),
    ("은어", "바닥 찍은 종목 찾고 싶어",
     L(q="'바닥'을 어떤 기준으로 볼까요?",
       choices=["52주 최저가 대비 상승률 10% 이하", "52주 최고가 대비 -40% 이하"]), "R2"),
    ("은어", "망할 것 같은 회사는 거르고 싶어",
     L(q="'망할 것 같다'를 어떤 기준으로 볼까요?",
       choices=["부채비율 200% 이하", "자본잠식 없음(자본잠식률 0%)"]), "R2"),
    # --- 20개 밖 지표 (R3) ---
    ("미지원", "ROE 15% 넘는 회사만 보여줘",
     L("unsupported_indicator", terms=["ROE"],
       msg="ROE는 아직 지원하지 않아요. 대신 매출순이익률이나 영업이익으로 원칙을 세워볼까요?"), "R3"),
    ("미지원", "이동평균선 골든크로스 난 종목",
     L("unsupported_indicator", terms=["골든크로스"],
       msg="이동평균선은 아직 지원하지 않아요. 대신 기간 수익률이나 52주 최저가 대비 상승률로 원칙을 세워볼까요?"), "R3"),
    ("미지원", "외국인이 많이 사는 종목",
     L("unsupported_indicator", terms=["외국인 순매수"],
       msg="외국인 매매 동향은 아직 지원하지 않아요. 대신 거래량 증가 배율이나 평균 거래대금으로 원칙을 세워볼까요?"), "R3"),
    ("미지원", "베타 낮은 종목이 좋아",
     L("unsupported_indicator", terms=["베타"],
       msg="베타는 아직 지원하지 않아요. 대신 최근 60거래일 변동성으로 원칙을 세워볼까요?"), "R3"),
    ("미지원", "ROE 10% 넘고 부채비율 100% 이하",
     L(conds=[c("DEBT_RATIO", "<=", 100)], terms=["ROE"],
       msg="ROE는 아직 지원하지 않아 부채비율 조건만 담았어요."), "R3 일부만 변환"),
    # --- 설명·관리·점검·범위 밖 (R5, R6) ---
    ("설명", "PER이 뭐야?", L("explain"), "R5"),
    ("설명", "PBR 낮으면 무조건 좋은 거야?", L("explain"), "R5"),
    ("관리", "방금 만든 원칙 저장해줘", L("manage"), "R5"),
    ("관리", "원칙 B 삭제할게", L("manage"), "R5"),
    ("점검", "이 원칙으로 6개월 전에 샀으면 어땠을까?", L("simulate"), "R5"),
    ("범위밖", "오늘 날씨 어때?",
     L("off_topic", msg="투자 원칙 점검과 관련된 질문에만 답할 수 있어요."), "R6 NFR-03"),
    ("범위밖", "삼성전자 지금 사도 돼?",
     L("off_topic", msg="매수 여부는 알려드리지 않아요. 저는 내 원칙에 맞는지 점검해 드려요."), "R6"),
    ("범위밖", "비트코인 추천해줘",
     L("off_topic", msg="종목이나 자산 추천은 하지 않아요. 투자 원칙 점검에 관한 질문을 해 주세요."), "R6"),
    ("범위밖", "안녕",
     L("off_topic", msg="안녕하세요! 투자 원칙을 말씀해 주시면 지표 조건으로 바꿔 드려요."), "R6 인사말 처리 팀 확인"),
]


# ---------- 오타 생성 ----------
def _is_syl(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3


def _split(ch):
    code = ord(ch) - 0xAC00
    return code // 588, (code % 588) // 28, code % 28


def _join(cho, jung, jong):
    return chr(0xAC00 + cho * 588 + jung * 28 + jong)


_VOWEL_SWAP = {1: 5, 5: 1, 8: 4, 4: 8}  # ㅐ<->ㅔ, ㅗ<->ㅓ


def make_typo(text, rng):
    """한글 단어(숫자·영문 없는 토큰)만 건드려 오타를 만든다. 원본과 다를 때까지 시도."""
    words = text.split(" ")
    cand = [i for i, w in enumerate(words)
            if len(w) >= 2 and all(_is_syl(ch) or ch in "?.,!" for ch in w)
            and sum(_is_syl(ch) for ch in w) >= 2]
    for _ in range(30):
        w2 = list(words)
        ops = rng.sample(["batchim", "swap", "vowel", "space"], k=rng.choice([1, 2]))
        for op in ops:
            if op == "space":
                j = rng.randrange(len(w2) - 1) if len(w2) > 1 else None
                if j is not None:
                    w2[j:j + 2] = [w2[j] + w2[j + 1]]
                continue
            if not cand:
                continue
            i = rng.choice(cand)
            if i >= len(w2) or w2[i] != words[i]:
                continue
            chars = list(w2[i])
            sy = [k for k, ch in enumerate(chars) if _is_syl(ch)]
            k = rng.choice(sy)
            cho, jung, jong = _split(chars[k])
            if op == "batchim" and jong:
                chars[k] = _join(cho, jung, 0)
            elif op == "vowel" and jung in _VOWEL_SWAP:
                chars[k] = _join(cho, _VOWEL_SWAP[jung], jong)
            elif op == "swap" and len(sy) >= 3:  # 2음절 단어는 교환하면 다른 단어가 되기 쉬움(회사->사회)
                k = rng.choice(sy[:-1])
                if sy[sy.index(k) + 1] == k + 1:
                    chars[k], chars[k + 1] = chars[k + 1], chars[k]
            w2[i] = "".join(chars)
        out = " ".join(w2)
        if out != text:
            return out
    return None


def main():
    pilot_path = HERE / "pilot_labels.jsonl"
    if not pilot_path.exists():
        print("pilot_labels.jsonl이 없음. 먼저 build_pilot.py를 실행하세요.")
        return 1
    pilot = [json.loads(line) for line in pilot_path.read_text(encoding="utf-8").splitlines() if line]

    base = []
    for r in pilot:
        base.append({"id": f"pilot-{r['id']}", "group": f"pilot-{r['id']}", "kind": "pilot",
                     "category": r["category"], "text": r["text"], "label": r["label"], "note": r["note"]})
    for n, (cat, text, label, note) in enumerate(NEW, 1):
        base.append({"id": f"new-{n:02d}", "group": f"new-{n:02d}", "kind": "new",
                     "category": cat, "text": text, "label": label, "note": note})

    rng = random.Random(SEED)
    typos = []
    for i, r in enumerate(base):
        if i % 2:  # 둘 중 하나꼴로 오타 변형을 붙인다
            continue
        t = make_typo(r["text"], rng)
        if t:
            typos.append({"id": f"typo-{r['id']}", "group": r["group"], "kind": "typo",
                          "category": r["category"], "text": t, "label": r["label"],
                          "note": f"오타 변형 원본: {r['text']}"})

    rows = base + typos
    bad = 0
    for r in rows:
        errs = validate(r["label"])
        if errs:
            bad += 1
            print(f"{r['id']} {r['text']}: {errs}")
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "id 중복"

    out = HERE / "dev_set.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    print(f"{len(rows)}개 저장, 검증 실패 {bad}개 -> {out}")
    print("종류:", dict(Counter(r["kind"] for r in rows)))
    print("intent:", dict(Counter(r["label"]["intent"] for r in rows)))
    print("되묻기:", sum(r["label"]["needs_clarification"] for r in rows),
          "/ 조건 확정 principle:", sum(r["label"]["intent"] == "principle" and not r["label"]["needs_clarification"] for r in rows))
    used = Counter(cd["indicator"] for r in rows for cd in r["label"]["conditions"])
    print("조건에 쓰인 지표:", len(used), "/ 20")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
