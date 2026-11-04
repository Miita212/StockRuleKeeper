"""H5 평가 세트 만들기: 문장과 정답 요약(아래 CASES)을 읽어 마스터·H3 값으로 정답 JSON을 채우고 eval_*.jsonl 로 저장한다.

- 시드(haechan H4)와 같은 문장이 있으면 멈춘다 (V9 규칙).
- 정답의 부등호·단위는 마스터에서 가져온다.

사용: python -I -X utf8 build_eval.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_common
from gen_common import SYSTEM
DATA = os.path.dirname(HERE)
BYUNGJUN = os.path.normpath(os.path.join(DATA, '..', '..', 'byungjun', 'data'))
HAECHAN = os.path.normpath(os.path.join(DATA, '..', '..', 'haechan', 'data'))

PERIOD_MESSAGE = '주가가 오른 정도는 기간에 따라 달라져요. 얼마 동안의 수익률로 볼까요?'
R1 = '저는 종목을 추천하지 않아요. 내 원칙에 맞는지는 판정서에서 확인해 볼 수 있어요.'
R2 = '저는 앞으로 오를지 내릴지는 말씀드릴 수 없어요. 원칙에 맞는 기준을 같이 정해 볼 수 있어요.'
R5 = '사고파는 시점은 알려 드리지 않아요. 내 원칙에 맞는 종목인지는 판정서에서 확인해 볼 수 있어요.'

M = {}
for f in glob.glob(os.path.join(BYUNGJUN, 'H1-*indicator_master*.json')):
    for r in json.load(open(f, encoding='utf-8')):
        M[r['id']] = r
H3 = {}
for f in glob.glob(os.path.join(BYUNGJUN, 'H3-[abc]_*.json')):
    for r in json.load(open(f, encoding='utf-8')):
        H3[r['id']] = r


# ---- 정답 만들기 -------------------------------------------------------
def answer(*items):
    """items = (id, 부등호, 값[, 기간]) 여러 개 -> 확정 정답 (20개 세트: 말한 지표 user, 나머지 default)"""
    anchors = {x[0]: x[2] for x in items}
    ops = {x[0]: x[1] for x in items}
    periods = [x[3] for x in items if len(x) > 3]
    return gen_common.gold_full(anchors, periods[0] if periods else None, ops)


def ask_value(i):
    h = H3[i]
    options = [dict(level=o['level'], label=o['label'], value=o['value']) for o in h['options']]
    return dict(needs_clarification=True, reason='VALUE_MISSING', indicator_id=i,
                message=h['clarify_message'], options=options)


def ask_which(message, ids):
    cands = [dict(id=i, label=M[i]['ui_name']) for i in ids]
    return dict(needs_clarification=True, reason='AMBIGUOUS_INDICATOR', message=message, candidates=cands)


def ask_period(known=None):
    d = dict(needs_clarification=True, reason='PERIOD_MISSING', indicator_id=15, message=PERIOD_MESSAGE,
             options=[dict(label='최근 %d개월' % m, months=m) for m in (1, 3, 6, 12)])
    if known:
        d['known'] = known
    return d


def refuse(message):
    return dict(refusal=True, message=message, indicators=[])


def out_of_list(term, similar_ids):
    names = '나 '.join(M[i]['ui_name'] for i in similar_ids)
    return refuse('%s는 아직 쓰지 않는 지표예요. %s 볼 수 있어요.' % (term, names))


# ---- 평가 문제 (문장, 종류, 정답) ---------------------------------------
CASES = {
    '1-7': [
        ('빚이 자기 돈의 두 배를 넘으면 안 돼요', '단일', answer((1, '<=', 200))),
        ('부채비율이 150퍼센트 미만이면 좋겠어', '단일(미만)', answer((1, '<', 150))),
        ('차입금의존도 25% 이하만 볼래요', '단일', answer((2, '<=', 25))),
        ('빌린 돈이 총자산의 10%를 못 넘는 회사', '단일', answer((2, '<=', 10))),
        ('이자보상배율 5배 이상인 곳', '단일(별칭)', answer((3, '>=', 5))),
        ('EBITDA가 금융비용의 4배 넘는 회사', '단일(초과)', answer((3, '>', 4))),
        ('자본잠식 없는 회사만 보고 싶어요', '단일(0%)', answer((4, '<=', 0))),
        ('자본잠식률 5% 이하', '단일', answer((4, '<=', 5))),
        ('영업이익이 흑자인 회사만 보여줘', '단일(흑자 = 0 초과)', answer((5, '>', 0))),
        ('영업이익 500억 이상 나는 회사', '단일(억원)', answer((5, '>=', 500))),
        ('영업이익 1조 넘는 회사', '단일(조 → 억원)', answer((5, '>', 10000))),
        ('5년 연속 영업흑자 낸 회사', '단일', answer((6, '>=', 5))),
        ('적어도 2년은 계속 흑자였던 회사', '단일', answer((6, '>=', 2))),
        ('순이익률 8퍼 넘는 회사', '단일(별칭)', answer((7, '>', 8))),
        ('매출순이익률이 10% 이상인 회사만', '단일', answer((7, '>=', 10))),
        ('부채비율 80% 이하이고 영업이익 흑자인 회사', '복수', answer((1, '<=', 80), (5, '>', 0))),
        ('차입금의존도 20% 이하에 4년 연속 흑자', '복수', answer((2, '<=', 20), (6, '>=', 4))),
        ('자본잠식 없고 매출순이익률 7% 이상인 곳', '복수', answer((4, '<=', 0), (7, '>=', 7))),
        ('이자보상배율 3배 이상이고 부채비율 120% 이하', '복수', answer((1, '<=', 120), (3, '>=', 3))),
        ('부채비률 100프로 이하만 보여줘', '오타', answer((1, '<=', 100))),
        ('빚 비율 50퍼 이하 회사 보고시퍼', '오타·구어', answer((1, '<=', 50))),
        ('영업리익 흑자인 회사만', '오타', answer((5, '>', 0))),
        ('빌린 돈에 많이 기대는 회사는 걸러줘', '되묻기(값 없음)', ask_value(2)),
        ('자본이 깎여 나간 회사는 싫어', '되묻기(값 없음)', ask_value(4)),
        ('이자를 잘 갚을 여유가 있는 회사였으면 좋겠어', '되묻기(값 없음)', ask_value(3)),
        ('영업이익이 높은 회사를 찾고 싶어요', '되묻기(값 없음)', ask_value(5)),
        ('흑자를 꾸준히 낸 회사', '되묻기(값 없음)', ask_value(6)),
        ('남는 장사하는 회사가 좋아', '되묻기(값 없음)', ask_value(7)),
        ('튼튼한 회사 위주로 보고 싶어요', '되묻기(지표 모호)',
         ask_which('튼튼하다고 볼 수 있는 기준이 여러 가지예요. 어떤 걸로 볼까요?', [1, 2, 4, 18])),
        ('빚 걱정 없는 회사만', '되묻기(지표 모호)',
         ask_which('빚 걱정은 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?', [1, 2, 3])),
        ('잘 버는 회사만 볼래요', '되묻기(지표 모호)',
         ask_which('잘 번다는 건 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?', [5, 6, 7])),
        ('망할 걱정 없는 회사', '되묻기(지표 모호)',
         ask_which('망할 걱정은 여러 가지로 볼 수 있어요. 어떤 걸로 볼까요?', [4, 5, 6])),
        ('ROA 높은 회사만 보여줘', '거절(20개 밖)', out_of_list('ROA', [7, 5])),
        ('현금 많이 쌓아둔 회사 찾아줘', '거절(20개 밖)', out_of_list('현금 보유액', [1, 2])),
        ('이 회사 지금 사도 돼?', '거절(종목 추천)', refuse(R1)),
        ('부채비율 낮은 회사 중에 제일 좋은 거 하나만 골라줘', '거절(종목 추천)', refuse(R1)),
    ],
    '8-13': [
        ('매출이 작년보다 20% 이상 늘어난 회사', '단일', answer((8, '>=', 20))),
        ('매출 성장률 10퍼 넘는 곳', '단일(별칭·초과)', answer((8, '>', 10))),
        ('매출액 증가율이 마이너스는 아닌 회사', '단일(0 이상)', answer((8, '>=', 0))),
        ('영업이익이 30% 넘게 늘어난 회사', '단일(초과)', answer((9, '>', 30))),
        ('영업이익 성장률 15% 이상', '단일(별칭)', answer((9, '>=', 15))),
        ('PER 12배 이하인 주식', '단일', answer((10, '<=', 12))),
        ('주가수익비율 8배 미만만 보여줘', '단일(별칭·미만)', answer((10, '<', 8))),
        ('PBR이 1배보다 낮은 회사', '단일(미만)', answer((11, '<', 1))),
        ('주가순자산비율 1.5배 이하', '단일(별칭·소수)', answer((11, '<=', 1.5))),
        ('배당수익률 4퍼센트 이상 주는 회사', '단일', answer((12, '>=', 4))),
        ('배당을 3% 넘게 주는 종목', '단일(초과)', answer((12, '>', 3))),
        ('10년 연속 배당한 회사', '단일', answer((13, '>=', 10))),
        ('배당을 7년 넘게 계속 준 회사', '단일(초과)', answer((13, '>', 7))),
        ('PER 10배 이하이고 PBR 1배 이하', '복수', answer((10, '<=', 10), (11, '<=', 1))),
        ('매출 20% 이상 늘고 영업이익도 20% 이상 늘어난 회사', '복수', answer((8, '>=', 20), (9, '>=', 20))),
        ('PBR 1배 미만이면서 배당수익률 3% 이상', '복수', answer((11, '<', 1), (12, '>=', 3))),
        ('배당 5년 이상 꾸준하고 PER 15배 이하', '복수', answer((10, '<=', 15), (13, '>=', 5))),
        ('매출 15% 성장하고 PER 20배 이하인 주식', '복수(영역 섞임)', answer((8, '>=', 15), (10, '<=', 20))),
        ('배당 수익율 3프로 이상', '오타', answer((12, '>=', 3))),
        ('매출 성장율 10% 이상인 회사', '오타', answer((8, '>=', 10))),
        ('PBR 0.8배 이하인 곳 보여조', '오타·구어', answer((11, '<=', 0.8))),
        ('이익에 비해 주가가 싼 주식', '되묻기(값 없음)', ask_value(10)),
        ('자산가치 대비 저렴한 회사', '되묻기(값 없음)', ask_value(11)),
        ('배당 많이 주는 회사', '되묻기(값 없음)', ask_value(12)),
        ('배당을 오래 챙겨 준 회사', '되묻기(값 없음)', ask_value(13)),
        ('매출이 쑥쑥 크는 회사', '되묻기(값 없음)', ask_value(8)),
        ('본업 이익이 빠르게 느는 회사', '되묻기(값 없음)', ask_value(9)),
        ('가성비 좋은 주식 찾아줘', '되묻기(지표 모호)',
         ask_which('가성비는 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?', [10, 11, 16])),
        ('이익이 늘어나는 회사가 좋아', '되묻기(지표 모호)',
         ask_which('이익이 늘어난다는 건 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?', [8, 9])),
        ('배당주 투자하고 싶어요', '되묻기(지표 모호)',
         ask_which('배당은 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?', [12, 13])),
        ('PEG 낮은 회사 찾아줘', '거절(20개 밖)', out_of_list('PEG', [10, 11])),
        ('배당 성장률 높은 회사', '거절(20개 밖)', out_of_list('배당 성장률', [12, 13])),
        ('EPS 증가율이 높은 회사만', '거절(20개 밖)', out_of_list('EPS 증가율', [8, 9])),
        ('ROIC 높은 기업만 보여줘', '거절(20개 밖)', out_of_list('ROIC', [7, 5])),
        ('배당 많이 주는 종목 중에 하나 골라줘', '거절(종목 추천)', refuse(R1)),
        ('이 주식 내년에도 배당 줄까?', '거절(예측)', refuse(R2)),
    ],
    '14-20': [
        ('시가총액 5천억 이상인 회사', '단일(억원)', answer((14, '>=', 5000))),
        ('시총 3조 넘는 대형주', '단일(조 → 억원)', answer((14, '>', 30000))),
        ('시가총액이 2000억은 되는 회사', '단일', answer((14, '>=', 2000))),
        ('시총 1000억 미만 작은 회사', '단일(반대 방향)', answer((14, '<', 1000))),
        ('최근 6개월 수익률이 15% 이상', '단일(기간)', answer((15, '>=', 15, 6))),
        ('한 달 동안 5% 이상 오른 종목', '단일(기간)', answer((15, '>=', 5, 1))),
        ('3개월 동안 마이너스인 종목은 제외해줘', '단일(기간)', answer((15, '>=', 0, 3))),
        ('고점 대비 -10% 이내인 종목', '단일(이내)', answer((16, '>=', -10))),
        ('52주 최고가보다 30% 넘게 떨어진 주식은 빼줘', '단일(이내)', answer((16, '>=', -30))),
        ('52주 최고가 대비 -15% 이내', '단일(이내)', answer((16, '>=', -15))),
        ('52주 저점에서 80% 넘게 오른 건 제외', '단일(이내)', answer((17, '<=', 80))),
        ('저점 대비 상승률이 30% 이내인 종목', '단일(이내)', answer((17, '<=', 30))),
        ('60일 변동성 3% 이하인 종목', '단일', answer((18, '<=', 3))),
        ('변동성이 1.5% 미만으로 잔잔한 종목', '단일(미만)', answer((18, '<', 1.5))),
        ('하루 평균 거래대금이 50억 이상인 종목', '단일', answer((19, '>=', 50))),
        ('20일 평균 거래대금 100억 넘는 종목', '단일(초과)', answer((19, '>', 100))),
        ('거래량이 평소의 3배 이상 터진 종목', '단일', answer((20, '>=', 3))),
        ('거래량 증가 배율 2배 이상', '단일', answer((20, '>=', 2))),
        ('시가총액 1조 이상이고 변동성 2% 이하', '복수', answer((14, '>=', 10000), (18, '<=', 2))),
        ('시총 5000억 넘고 거래대금 20억 이상', '복수', answer((14, '>', 5000), (19, '>=', 20))),
        ('고점 대비 -20% 이내이면서 3개월 수익률 10% 이상', '복수(기간)', answer((15, '>=', 10, 3), (16, '>=', -20))),
        ('거래량 2배 이상 늘었고 시총 3000억 이상', '복수', answer((14, '>=', 3000), (20, '>=', 2))),
        ('시총 1조 이상인 회사만 볼래여', '오타·구어', answer((14, '>=', 10000))),
        ('변동선 2프로 이하인 종목', '오타', answer((18, '<=', 2))),
        ('너무 작은 회사는 싫어', '되묻기(값 없음)', ask_value(14)),
        ('고점에서 많이 안 떨어진 종목', '되묻기(값 없음)', ask_value(16)),
        ('저점에서 아직 안 오른 종목', '되묻기(값 없음)', ask_value(17)),
        ('주가가 잔잔한 종목이 좋아', '되묻기(값 없음)', ask_value(18)),
        ('거래대금 큰 종목', '되묻기(값 없음)', ask_value(19)),
        ('거래가 갑자기 늘어난 종목', '되묻기(값 없음)', ask_value(20)),
        ('요즘 주가가 오른 종목', '되묻기(기간 없음)', ask_period()),
        ('최근 주가가 많이 내린 종목', '되묻기(기간 없음)', ask_period()),
        ('20% 넘게 오른 종목', '되묻기(기간 없음)', ask_period(dict(operator='>', value=20, unit='%'))),
        ('주가가 롤러코스터 같은 종목', '되묻기(지표 모호)',
         ask_which('출렁임은 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?', [16, 18])),
        ('규모가 큰 회사', '되묻기(지표 모호)',
         ask_which('크다는 건 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?', [14, 19])),
        ('MACD 골든크로스 난 종목', '거절(20개 밖)', out_of_list('MACD', [15, 16])),
        ('기관이 많이 사는 종목', '거절(20개 밖)', out_of_list('기관 순매수', [19, 20])),
        ('이 종목 지금 팔아야 할까?', '거절(매매 시점)', refuse(R5)),
        ('대박 날 종목 하나만 알려줘', '거절(예측)', refuse(R2)),
    ],
}


def seed_sentences():
    out = set()
    for f in glob.glob(os.path.join(HAECHAN, 'seed_*.jsonl')):
        for line in open(f, encoding='utf-8'):
            out.add(norm(json.loads(line)['messages'][1]['content']))
    return out


def norm(text):
    return ''.join(c for c in text.lower() if c.isalnum())


seeds = seed_sentences()
seen = set()
for name, cases in CASES.items():
    path = os.path.join(DATA, 'eval_%s.jsonl' % name)
    prefix = {'1-7': 'H5a', '8-13': 'H5b', '14-20': 'H5c'}[name]
    with open(path, 'w', encoding='utf-8') as fp:
        for n, (text, kind, gold) in enumerate(cases, 1):
            key = norm(text)
            assert key not in seeds, '시드와 같은 문장: ' + text
            assert key not in seen, '평가 세트 안에서 중복: ' + text
            seen.add(key)
            rec = dict(type='EVAL', eval_id='%s-%03d' % (prefix, n), id='%s-%03d' % (prefix, n), kind=kind, text=text, output=gold,
                       messages=[dict(role='system', content=SYSTEM), dict(role='user', content=text),
                                 dict(role='assistant', content=json.dumps(gold, ensure_ascii=False))])
            fp.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(path, len(cases), '문제')
