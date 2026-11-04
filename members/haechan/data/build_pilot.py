"""시범 라벨 33개를 만들고 스키마로 검증해 pilot_labels.jsonl로 저장한다.

실행: python members/haechan/data/build_pilot.py

라벨 규칙 (초안, 팀 확정 전):
 R1. 수치가 명확하면 조건으로 확정한다 (되묻기 없음).
 R2. 수치가 없으면 추측하지 않고 되묻는다. choices는 2~3개, 각 선택지에 지표와 수치를 넣는다.
 R3. 지표 20개로 표현할 수 없으면 억지로 바꾸지 않는다.
     - 전부 못 바꾸면 unsupported_indicator, 일부만 바꾸면 principle + unsupported_terms.
 R4. 가장 가까운 지표가 있어도 기간·정의가 다르면 되묻기로 보여 준다 (예: 1년 변동성 -> 60거래일 변동성).
 R5. 설명 요청은 explain, 앱 조작은 manage, 점검 요청은 simulate. 조건은 비운다.
 R6. 종목 추천, 목표주가, 원금 보장, 알림 등은 off_topic이고 message로 점검 서비스임을 안내한다.
 R7. 단위는 indicators.py의 잠정 단위를 따른다 (시가총액 억원 등).
note는 학습에 쓰지 않는 검수용 메모이며 팀에서 정해야 할 점을 적는다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from llm.schema import validate  # noqa: E402


def c(ind, op, val, pm=None):
    d = {"indicator": ind, "op": op, "value": val}
    if pm is not None:
        d["period_months"] = pm
    return d


def L(intent="principle", conds=None, q=None, choices=None, terms=None, msg=None):
    return {"intent": intent, "needs_clarification": bool(q),
            "question": q, "choices": choices or [], "conditions": conds or [],
            "unsupported_terms": terms or [], "message": msg}


# (번호, 카테고리, 질문, 라벨, note)
ROWS = [
    (48, "부채", "부채비율 80% 이하인 데 있어?",
     L(conds=[c("DEBT_RATIO", "<=", 80)]), ""),
    (31, "부채", "빚 많은 회사는 무서우니까 부채비율 낮은 곳으로 알려줘.",
     L(q="부채비율 기준을 어느 정도로 할까요?",
       choices=["부채비율 100% 이하", "부채비율 200% 이하"]), "R2"),
    (70, "부채", "부채비율만 보고 튼튼한 회사인지 알 수 있어?", L("explain"), "R5"),
    (9, "부채", "단기 빚이 많은 기업은 싫어요",
     L(q="단기 차입만 따로 보는 지표는 없어요. 전체 차입금 비중(차입금의존도)으로 볼까요?",
       choices=["차입금의존도 30% 이하", "차입금의존도 50% 이하"]), "R4"),
    (93, "부실", "투자경고 뜬 종목은 일단 걸러줘.",
     L("unsupported_indicator", terms=["투자경고 종목"],
       msg="투자경고·관리종목 같은 부실 종목은 판정 전에 기본으로 제외돼요. 따로 설정하지 않아도 돼요."),
     "필터 항목(부실 플래그)의 처리 방식 팀 확정 필요"),
    (89, "부실", "자본이 마이너스인 회사는 무조건 제외해줘.",
     L(conds=[c("CAPITAL_IMPAIRMENT", "<", 100)]),
     "자본잠식률 100% = 완전잠식이라는 정의 확인 필요"),
    (195, "수익성", "몇 년째 계속 흑자인 회사가 좋아.",
     L(q="몇 년 연속 영업흑자를 기준으로 할까요?",
       choices=["3년 연속", "5년 연속", "10년 연속"]), "R2 선택지 값은 지표 기준 0~30년 범위"),
    (128, "수익성", "EBITDA 마진 높은 회사 원해요",
     L("unsupported_indicator", terms=["EBITDA 마진"],
       msg="EBITDA 마진은 아직 지원하지 않아요. 대신 매출순이익률이나 영업이익으로 원칙을 세워볼까요?"), "R3"),
    (133, "수익성", "주당순이익(EPS) 증가하는 회사만 하고싶음",
     L("unsupported_indicator", terms=["EPS"],
       msg="EPS는 아직 지원하지 않아요. 대신 영업이익 증가율로 원칙을 세워볼까요?"), "R3"),
    (285, "밸류", "싼 주식 찾고 싶어.",
     L(q="'싸다'를 어떤 기준으로 볼까요?",
       choices=["PER 10배 이하", "PBR 1배 이하", "PER 10배 이하 + PBR 1배 이하"]), "R2"),
    (244, "밸류", "적정주가 대비 20% 싼 가격에서만 사고싶음",
     L("unsupported_indicator", terms=["적정주가"],
       msg="적정주가 계산은 지원하지 않아요. 대신 PER이나 PBR 기준으로 원칙을 세워볼까요?"), "R3"),
    (296, "밸류", "PBR이 마이너스인 건 무슨 뜻이야?", L("explain"), "R5"),
    (324, "성장", "컨센서스 상회하는 회사만 하고싶은데 가능?",
     L("unsupported_indicator", terms=["컨센서스"],
       msg="컨센서스 비교는 지원하지 않아요. 대신 매출액이나 영업이익 증가율로 원칙을 세워볼까요?"), "R3"),
    (371, "성장", "영업이익이 계속 늘고 있는 회사가 좋아.",
     L(q="영업이익 증가율을 얼마 이상으로 할까요?",
       choices=["0% 초과", "10% 이상", "20% 이상"]),
     "'계속'(다년 연속 증가)을 표현할 지표가 없음. 증가율 1개로 대체해도 되는지 팀 확인"),
    (410, "배당", "배당만으로 연 5% 받고싶음 가능한 원칙 짜줘",
     L(conds=[c("DIVIDEND_YIELD_12M", ">=", 5)]), "R1"),
    (465, "배당", "나는 배당 없어도 되니까 배당 조건은 넣지 마.",
     L("manage"), "원칙 편집 지시로 분류. 팀 확인"),
    (575, "규모", "시총 3조 이상 되는 믿음직한 녀석.",
     L(conds=[c("MARKET_CAP", ">=", 30000)]), "R1 3조원 = 30,000억원"),
    (542, "규모", "작전주 같은 소형주는 거르고싶음",
     L(q="소형주를 시가총액 얼마 기준으로 거를까요?",
       choices=["시가총액 1,000억원 이상", "시가총액 3,000억원 이상", "시가총액 1조원 이상"]), "R2"),
    (611, "변동성", "1년 변동성 20% 이하 종목",
     L(q="변동성은 최근 60거래일 기준으로만 볼 수 있어요. 이 기준으로 할까요?",
       choices=["최근 60거래일 변동성 20% 이하", "최근 60거래일 변동성 30% 이하"]),
     "R4. 변동성 단위(연환산 여부) 확인 필요"),
    (628, "변동성", "신용잔고율 높은 종목 거르고싶음",
     L("unsupported_indicator", terms=["신용잔고율"],
       msg="신용잔고율은 아직 지원하지 않아요. 대신 변동성이나 거래량 지표로 원칙을 세워볼까요?"), "R3 확장 지표"),
    (613, "변동성", "52주 최저가 근처 종목은 위험하니까 제외할래",
     L(q="52주 최저가보다 얼마 이상 오른 종목만 남길까요?",
       choices=["10% 이상", "20% 이상", "30% 이상"]), "R2"),
    (708, "모멘텀", "반토막 난 회사는 피하고 싶어.",
     L(q="'반토막'을 어떤 기준으로 볼까요?",
       choices=["52주 최고가 대비 -50% 초과", "최근 12개월 수익률 -50% 초과"]), "R4"),
    (783, "복합", "부채비율 100% 이하에 PER 15 이하인 안전빵 저평가.",
     L(conds=[c("DEBT_RATIO", "<=", 100), c("PER", "<=", 15)]), "R1"),
    (813, "복합", "빚 적고 배당 많은 회사를 찾고 싶어.",
     L(q="빚과 배당을 어느 정도로 볼까요?",
       choices=["부채비율 100% 이하 + 배당수익률 3% 이상",
                "부채비율 200% 이하 + 배당수익률 2% 이상"]), "R2"),
    (870, "모호", "동전주 나부랭이 말고 진짜 주식.",
     L("unsupported_indicator", terms=["동전주"],
       msg="동전주(저가주) 제외는 아직 지원하지 않아요. 대신 시가총액 기준으로 원칙을 세워볼까요?"),
     "동전주는 가격 필터. 필터 항목 처리 방식 팀 확정 필요"),
    (992, "범위밖", "원금 절대 안 잃는 주식으로 찾아줘.",
     L("off_topic", msg="원금 보장은 어떤 지표로도 확인할 수 없어요. 대신 부채비율이나 연속 흑자처럼 안정성을 보는 원칙을 세워볼까요?"),
     "R6"),
    (989, "범위밖", "이거 통과하면 지금 사라는 뜻이야?", L("explain"),
     "앱의 고정 안내문(매수 권유 아님)을 보여 주는 용도. 설명문 위치 팀 확정 필요"),
    (1015, "범위밖", "이 종목 목표주가 얼마로 보면돼?",
     L("off_topic", msg="목표주가는 알려드리지 않아요. 저는 내 원칙에 맞는지 점검해 드려요."), "R6"),
    (1002, "범위밖", "목표가 되면 카톡으로 알림 보내줄수있어?",
     L("off_topic", msg="알림 기능은 지원하지 않아요. 투자 원칙 점검에 관한 질문을 해 주세요."), "R6"),
    (925, "관리", "수정안 승인할게 반영해줘", L("manage"), "R5"),
    (963, "점검", "원칙 점검 해줘", L("simulate"), "R5"),
    (966, "점검", "원칙 A랑 B 중 과거에 뭐가 더 나았는지 비교해줘.", L("simulate"), "R5"),
    (982, "점검", "이 시기에 금리나 환율 때문에 결과가 달랐을 수도 있어?", L("explain"), "R5"),
]


def main():
    bad = 0
    out = []
    for no, cat, text, label, note in ROWS:
        errs = validate(label)
        if errs:
            bad += 1
            print(f"#{no} {text}: {errs}")
        out.append({"id": no, "category": cat, "text": text, "label": label, "note": note})
    p = HERE / "pilot_labels.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
    print(f"{len(out)}개 저장, 검증 실패 {bad}개 -> {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
