"""S-2, S-3 생성기가 같이 쓰는 도구: 마스터·H3·동의어 읽기, 20개 세트 만들기, 말풍선 문장.

생성은 템플릿과 규칙만 쓴다 (외부 LLM 사용 안 함, D6 결론).
"""
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
MEMBERS = os.path.normpath(os.path.join(DATA, '..', '..'))
BYUNGJUN = os.path.join(MEMBERS, 'byungjun', 'data')
YAPPANG = os.path.join(MEMBERS, 'yappang', 'data')

SYSTEM = ('너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. '
          'JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아.')  # haechan 시드(H4)와 같은 문구
OP_WORD = {'<=': '이하', '>=': '이상', '<': '미만', '>': '초과'}
OP_JOSA = {'<=': '이하로', '>=': '이상으로', '<': '미만으로', '>': '초과로'}  # 부등호 말 + 조사

M = {}
for f in glob.glob(os.path.join(BYUNGJUN, 'H1-*indicator_master*.json')):
    for r in json.load(open(f, encoding='utf-8')):
        M[r['id']] = r
H3 = {}
for f in glob.glob(os.path.join(BYUNGJUN, 'H3-[abc]_*.json')):
    for r in json.load(open(f, encoding='utf-8')):
        H3[r['id']] = r
AREAS = []  # 마스터 순서대로 영역 이름
for i in range(1, 21):
    if M[i]['area'] not in AREAS:
        AREAS.append(M[i]['area'])


def load_synonyms():
    """동의어 사전 -> [{'id', 'text', 'overlap': [id...], 'memo'}]"""
    rows = []
    for f in sorted(glob.glob(os.path.join(YAPPANG, 'synonyms_*.csv'))):
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            overlap = [int(x) for x in r['겹침_지표번호'].split(',') if x.strip()]
            rows.append(dict(id=int(r['지표번호']), text=r['표현'].strip(), overlap=overlap, memo=r['메모'], kind=r['유형']))
    return rows


def plain(row):
    """값·방향이 없는 평범한 표현인지 (숫자 없음, 반대 방향 아님)"""
    return not any(c.isdigit() for c in row['text']) and '반대' not in row['memo']


# ---- 값을 말로 ------------------------------------------------------------
def num(v):
    return str(int(v)) if float(v) == int(v) else str(v)


def value_text(v, unit):
    """정답 표기 (50% / 3배 / 4년 / 5000억원)"""
    return num(v) + unit


def spoken_variants(v, unit):
    """사용자가 직접 말할 때의 숫자 표현들"""
    n = num(v)
    if unit == '억원':
        out = [n + '억']
        if v >= 10000 and v % 10000 == 0:
            out.append(num(v // 10000) + '조')
        if v >= 1000 and v % 1000 == 0:
            out.append(num(v // 1000) + '천억')
        return out
    if unit == '%':
        return [n + '%', n + '퍼센트']
    return [n + unit]


# ---- 정답 JSON ------------------------------------------------------------
def gold_full(anchors, period=None, ops=None):
    """말한 지표는 source=user, 나머지는 마스터 기본값 source=default. anchors = {id: 값}"""
    ops = ops or {}
    inds = []
    for i in range(1, 21):
        m = M[i]
        if i in anchors:
            d = dict(id=i, operator=ops.get(i, m['operator']), value=anchors[i], unit=m['unit'], source='user')
        else:
            d = dict(id=i, operator=m['operator'], value=m['default'], unit=m['unit'], source='default')
        if i == 15 and i in anchors:  # 기본값 항목에는 기간을 붙이지 않는다 (haechan 확인)
            d['period_months'] = period
        inds.append(d)
    return dict(indicators=inds, anchors=sorted(anchors))


def ask_value(i, period=None):
    h = H3[i]
    d = dict(needs_clarification=True, reason='VALUE_MISSING', indicator_id=i, message=h['clarify_message'],
             options=[dict(level=o['level'], label=o['label'], value=o['value']) for o in h['options']])
    if period:
        d['period_months'] = period
    return d


def ask_period():
    return dict(needs_clarification=True, reason='PERIOD_MISSING', indicator_id=15,
                message='주가가 오른 정도는 기간에 따라 달라져요. 얼마 동안의 수익률로 볼까요?',
                options=[dict(label='최근 %d개월' % m, months=m) for m in (1, 3, 6, 12)])


def bubble(i, option, period=None, op=None):
    """설명 말풍선: [기준 문장] [이유 문장(H3 reason)] [바꿀 수 있다는 안내]"""
    m = M[i]
    op = op or m['operator']
    name = m['ui_name']
    if period:
        name = '최근 %d개월 %s' % (period, name)
    return '%s 기준을 %s %s 잡았어요. %s 나중에 바꿀 수 있어요.' % (
        name, value_text(option['value'], m['unit']), OP_JOSA[op], option['reason'].rstrip('.') + '.')


def final_answer(i, option, period=None):
    d = gold_full({i: option['value']}, period)
    d['explain_bubble'] = bubble(i, option, period)
    return d


def dump(obj):
    return json.dumps(obj, ensure_ascii=False)


def msg(role, content):
    return dict(role=role, content=content if isinstance(content, str) else dump(content))
