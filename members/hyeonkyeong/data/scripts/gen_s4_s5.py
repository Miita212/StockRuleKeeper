"""S-3: S4 수정 diff + S5 거절 생성 -> gen_s4_s5.jsonl

S4 입력 형식 [제안]
    현재 원칙: {"indicators": [{id, operator, value, unit, source, (locked: true), (period_months)} x 20]}
    요청: <사용자 말>
S4 정답
    {"changes": [{id, name, before, after, unit}], "skipped_locked": [잠겨서 못 바꾼 지표 id]}
  - 잠긴 지표는 절대 바꾸지 않는다. 잠긴 지표만 건드리는 요청은 만들지 않는다.
  - "전체적으로 ~하게" 요청은 사용자가 직접 말한(source=user) 지표 중 잠기지 않은 것만 바꾼다. [제안]
  - '더 엄격하게'의 크기는 마스터 step_stricter 규칙, '더 느슨하게'는 그 반대로 되돌리는 크기. [제안]
S5: 종목 추천·예측·매매 시점·보장·20개 밖 지표·투자 무관 -> {"refusal": true, "message": ..., "indicators": []}

문장은 템플릿으로 만든다 (외부 LLM 사용 안 함). 시드·평가 세트와 같은 문장은 건너뛴다.

사용: python -I -X utf8 gen_s4_s5.py
"""
import glob
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_common import *

random.seed(45)
HAECHAN = os.path.join(MEMBERS, 'haechan', 'data')
N_EXPLICIT, N_RELATIVE, N_MULTI, N_GLOBAL = 220, 220, 130, 130


def norm(text):
    return ''.join(c for c in text.lower() if c.isalnum())


# 이미 있는 문장(시드, 평가, 다른 사람 S-4)과 겹치면 건너뛴다
taken = set()
for pattern in [os.path.join(HAECHAN, 'seed_*.jsonl'), os.path.join(DATA, 'eval_*.jsonl'),
                os.path.join(BYUNGJUN, 'S-4_gen_s6_s7.jsonl')]:
    for f in glob.glob(pattern):
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            taken.add(norm(' '.join(m['content'] for m in r['messages'] if m['role'] == 'user')))


# ---- 값 계산 ----------------------------------------------------------------
def clean(x, unit='%'):
    x = round(x) if unit == '억원' else round(x, 2)  # 금액은 억원 정수
    return int(x) if x == int(x) else x


def batchim(word):
    """마지막 글자의 받침 번호 (0 = 받침 없음, 8 = ㄹ). 한글이 아니면 0"""
    c = word[-1]
    return (ord(c) - ord('가')) % 28 if '가' <= c <= '힣' else 0


def list_text(names):
    """['매출순이익률', '영업이익'] -> '매출순이익률이나 영업이익으로'"""
    first, last = names[0], names[-1]
    return '%s%s %s%s' % (first, '이나' if batchim(first) else '나', last, '로' if batchim(last) in (0, 8) else '으로')


def step(i, v, stricter):
    """더 엄격(stricter=True) 또는 더 느슨하게 했을 때의 새 값. 못 바꾸면 None. 규칙은 마스터 step_stricter 문구를 코드로 옮긴 것"""
    m = M[i]
    if i in (1, 2, 10, 11, 17, 18):          # 20% 낮춤이 엄격 (17은 20% 낮춤)
        new = v * 0.8 if stricter else v / 0.8
    elif i in (3, 7, 12, 14, 19, 20):        # 20% 높임이 엄격
        new = v * 1.2 if stricter else v / 1.2
    elif i == 4:                             # 0이면 그대로, 아니면 20% 낮춤
        if v == 0:
            return None
        new = v * 0.8 if stricter else v / 0.8
    elif i == 5:                             # 0이면 100억원, 이미 양수면 2배
        if stricter:
            new = 100 if v == 0 else v * 2
        else:
            new = None if v <= 0 else (0 if v == 100 else v / 2)
        if new is None:
            return None
    elif i in (6, 13):                       # 1년 늘림
        new = v + 1 if stricter else v - 1
    elif i in (8, 9):                        # 20% 높임 (0이면 5%p)
        if v == 0:
            new = 5 if stricter else None
        else:
            new = v * 1.2 if stricter else v / 1.2
        if new is None:
            return None
    else:                                    # 15, 16: 5%p 이동
        new = v + 5 if stricter else v - 5
    new = clean(new, m['unit'])
    if new == v or new < m['min'] or new > m['max']:
        return None
    return new


def name_for_request(i):
    m = M[i]
    return random.choice([m['name'], m['ui_name'], m['abbr']])


def make_state():
    """현재 원칙: 사용자가 말한 지표 1~3개(source=user) + 나머지 기본값"""
    n = random.choice([1, 2, 2, 3])
    ids = random.sample(range(1, 21), n)
    anchors = {}
    for i in ids:
        anchors[i] = random.choice(H3[i]['options'])['value']
    period = random.choice([1, 3, 6, 12])
    state = gold_full(anchors, period)['indicators']
    return state, sorted(anchors)


def lock(state, ids):
    for e in state:
        if e['id'] in ids:
            e['locked'] = True


def value_of(state, i):
    return next(e['value'] for e in state if e['id'] == i)


def new_value_options(state, i):
    """말로 바꿀 수 있는 새 값 후보: H3 선택지 값 + 단계 값 중 현재와 다른 것"""
    cur = value_of(state, i)
    vals = [o['value'] for o in H3[i]['options']]
    for stricter in (True, False):
        s = step(i, cur, stricter)
        if s is not None:
            vals.append(s)
    return [v for v in vals if v != cur and M[i]['min'] <= v <= M[i]['max']]


def change(i, before, after):
    return dict(id=i, name=M[i]['ui_name'], before=before, after=after, unit=M[i]['unit'])


# ---- 요청 문장 ---------------------------------------------------------------
STRICT_WORDS = ['더 엄격하게', '좀 더 빡빡하게', '더 깐깐하게']
LOOSE_WORDS = ['더 느슨하게', '조금 느슨하게', '좀 완화해서']


def explicit_part(i, v):
    m = M[i]
    return '%s 기준 %s %s' % (name_for_request(i), random.choice(spoken_variants(v, m['unit'])), OP_JOSA[m['operator']])


def relative_part(i, stricter):
    return '%s 기준 %s' % (name_for_request(i), random.choice(STRICT_WORDS if stricter else LOOSE_WORDS))


def plan_target(state, i):
    """지표 i를 어떻게 바꿀지: (문장 조각, 새 값). 바꿀 수 없으면 None"""
    cur = value_of(state, i)
    if random.random() < 0.5:
        options = new_value_options(state, i)
        if not options:
            return None
        v = random.choice(options)
        return explicit_part(i, v), v
    stricter = random.random() < 0.5
    v = step(i, cur, stricter)
    if v is None:
        return None
    return relative_part(i, stricter), v


def sample(kind, state, request, answer, locked):
    text = '현재 원칙: %s\n요청: %s' % (dump(dict(indicators=state)), request)
    key = norm(text)
    if key in taken:
        return
    taken.add(key)
    out.append(dict(type='S4', kind=kind, indicator_ids=sorted({c['id'] for c in answer['changes']}),
                    locked=sorted(locked),
                    messages=[msg('system', SYSTEM), msg('user', text), msg('assistant', answer)]))


out = []

# ---- S4-1 값을 말해서 바꾸기 / S4-2 더 엄격·느슨하게 (지표 1개) --------------------
for kind, goal, mode in [('S4 값 지정', N_EXPLICIT, 'explicit'), ('S4 상대 요청', N_RELATIVE, 'relative')]:
    made = 0
    while made < goal:
        state, anchors = make_state()
        i = random.choice(range(1, 21))
        locked_ids = {x for x in random.sample(range(1, 21), random.choice([0, 1, 2, 3])) if x != i}
        cur = value_of(state, i)
        if mode == 'explicit':
            options = new_value_options(state, i)
            if not options:
                continue
            v = random.choice(options)
            part = explicit_part(i, v)
            request = random.choice(['%s 바꿔 줘', '%s 맞춰 줘', '%s 바꿀래요']) % part
        else:
            stricter = random.random() < 0.5
            v = step(i, cur, stricter)
            if v is None:
                continue
            request = random.choice(['%s 바꿔 줘', '%s 해 줘', '%s 해주세요']) % relative_part(i, stricter)
        lock(state, locked_ids)
        before = len(out)
        sample(kind, state, request, dict(changes=[change(i, cur, v)]), locked_ids)
        made += len(out) - before

# ---- S4-3 여러 지표를 한 번에 (잠긴 것은 건너뜀) -----------------------------------
made = 0
while made < N_MULTI:
    state, anchors = make_state()
    a, b = random.sample(range(1, 21), 2)
    pa, pb = plan_target(state, a), plan_target(state, b)
    if pa is None or pb is None:
        continue
    locked_ids = set()
    if random.random() < 0.5:
        locked_ids.add(random.choice([a, b]))
    locked_ids |= {x for x in random.sample(range(1, 21), random.choice([0, 1])) if x not in (a, b)}
    changes = [change(i, value_of(state, i), v) for i, v in ((a, pa[1]), (b, pb[1])) if i not in locked_ids]
    skipped = [i for i in (a, b) if i in locked_ids]
    if not changes:
        continue
    changes.sort(key=lambda c: c['id'])
    answer = dict(changes=changes)
    if skipped:
        answer['skipped_locked'] = sorted(skipped)
    lock(state, locked_ids)
    request = '%s, %s 바꿔 줘' % (pa[0], pb[0])
    before = len(out)
    sample('S4 여러 지표', state, request, answer, locked_ids)
    made += len(out) - before

# ---- S4-4 전체적으로 (사용자가 말한 지표 중 잠기지 않은 것만) --------------------------
GLOBAL_STRICT = ['전체적으로 조금 더 엄격하게 해 줘', '원칙을 한 단계 더 빡빡하게 바꿔 줘', '조건을 전반적으로 더 깐깐하게 해줘']
GLOBAL_LOOSE = ['조건을 조금 느슨하게 해 줘', '전체적으로 좀 풀어 줘', '원칙을 전반적으로 더 느슨하게 바꿔 줘']
made = 0
while made < N_GLOBAL:
    state, anchors = make_state()
    stricter = random.random() < 0.5
    locked_ids = set()
    if len(anchors) >= 2 and random.random() < 0.7:
        locked_ids.add(random.choice(anchors))
    changes = []
    for i in anchors:
        if i in locked_ids:
            continue
        v = step(i, value_of(state, i), stricter)
        if v is not None:
            changes.append(change(i, value_of(state, i), v))
    if not changes:
        continue
    answer = dict(changes=changes)
    skipped = sorted(locked_ids)
    if skipped:
        answer['skipped_locked'] = skipped
    lock(state, locked_ids)
    before = len(out)
    sample('S4 전체 요청', state, random.choice(GLOBAL_STRICT if stricter else GLOBAL_LOOSE), answer, locked_ids)
    made += len(out) - before

# ---- S5 거절 ------------------------------------------------------------------
R1 = '저는 종목을 추천하지 않아요. 내 원칙에 맞는지는 판정서에서 확인해 볼 수 있어요.'
R2 = '저는 앞으로 오를지 내릴지는 말씀드릴 수 없어요. 원칙에 맞는 기준을 같이 정해 볼 수 있어요.'
R4 = '저는 투자 원칙을 세우는 일만 도와드려요. 보고 싶은 기준이 있으면 말씀해 주세요.'
R5 = '사고파는 시점은 알려 드리지 않아요. 내 원칙에 맞는 종목인지는 판정서에서 확인해 볼 수 있어요.'
R6 = '손실이 없는 종목은 알려 드릴 수 없어요. 빚이나 변동성 같은 기준으로 조건을 세워 볼 수 있어요.'

SUBJECTS = ['삼성전자', 'SK하이닉스', '카카오', '네이버', '현대차', '이 종목', '이 회사', '이 주식', '그 종목']


def refusal(kind, text, message):
    key = norm(text)
    if key in taken:
        return
    taken.add(key)
    out.append(dict(type='S5', kind=kind, indicator_ids=[],
                    messages=[msg('system', SYSTEM), msg('user', text),
                              msg('assistant', dict(refusal=True, message=message, indicators=[]))]))


for s in SUBJECTS:
    for t in ['%s 지금 사도 돼?', '%s 사는 게 좋을까요?', '%s 추천해줘', '%s 지금 들어가도 될까?', '%s 담아도 괜찮아요?',
              '%s 매수해도 될까요?', '%s 지금 사면 후회할까?']:
        refusal('S5 종목 추천', t % s, R1)
    for t in ['%s 내일 오를까?', '%s 내년 주가 어떻게 될까요?', '%s 곧 오를 것 같아?', '%s 앞으로 떨어질까요?']:
        refusal('S5 예측', t % s, R2)
    for t in ['%s 언제 팔아야 해?', '%s 지금 손절해야 할까요?', '%s 더 들고 있어도 될까?']:
        refusal('S5 매매 시점', t % s, R5)
for t in ['다음 달에 오를 종목 알려줘', '곧 폭등할 종목 있어?', '내일 급등할 주식 하나만 알려줘요', '올해 제일 많이 오를 종목이 뭐야?',
          '수익률 제일 좋을 종목 찍어줘', '이번 주에 오를 주식 알려주세요', '대박 날 종목 좀 알려줘', '가장 유망한 종목 하나만 골라줘']:
    refusal('S5 예측', t, R2)
for t in ['절대 안 망하는 종목만 알려줘', '손해 안 보는 주식 있어?', '원금 보장되는 종목 알려주세요', '무조건 수익 나는 종목 알려줘',
          '잃을 일 없는 종목만 보여줘', '확실하게 버는 종목 있나요?']:
    refusal('S5 보장 요구', t, R6)
for t in ['오늘 날씨 어때?', '김치찌개 레시피 알려줘', '파이썬 코드 짜 줘', '영화 하나 추천해줘', '너 이름이 뭐야?', '점심 뭐 먹을까?',
          '영어 번역해 줘', '주말에 어디 놀러 갈까요?', '오늘 기분이 안 좋아', '노래 가사 써 줘', '여행 계획 짜 줘',
          '숙제 도와줘', '로또 번호 알려줘', '내 사주 좀 봐줘', '농담 하나 해 줘', '운동 루틴 알려 주세요']:
    refusal('S5 투자 무관', t, R4)

# 20개 밖 지표: (표현, 조사, 비슷한 지표 id)
OUTSIDE = [('ROE', '는', [7, 5]), ('ROA', '는', [7, 5]), ('유동비율', '은', [1, 2]), ('당좌비율', '은', [1, 2]),
           ('EPS', '는', [7, 5]), ('BPS', '는', [11, 1]), ('배당성향', '은', [12, 13]), ('RSI', '는', [15, 18]),
           ('MACD', '는', [15, 16]), ('이동평균선', '은', [15, 16]), ('베타', '는', [18, 16]), ('PSR', '은', [10, 11]),
           ('EV/EBITDA', '는', [10, 11]), ('외국인 순매수', '는', [19, 20]), ('기관 순매수', '는', [19, 20]),
           ('PEG', '는', [10, 11]), ('ROIC', '는', [7, 5]), ('잉여현금흐름', '은', [3, 5]), ('영업이익률', '은', [7, 5]),
           ('공매도 비율', '은', [19, 20]), ('신용잔고', '는', [19, 20]), ('자사주 매입', '은', [12, 13])]
TEMPLATES = ['%s 높은 회사만 보여줘', '%s 낮은 종목 찾아줘', '%s 좋은 회사 알려줘', '%s 기준으로 골라 줘', '%s 괜찮은 종목만 보고 싶어요']
VALUES = ['10% 이상', '5 이하', '20 넘는', '3 이상']
for term, josa, similar in OUTSIDE:
    names = list_text([M[i]['ui_name'] for i in similar])
    message = '%s%s 아직 쓰지 않는 지표예요. %s 볼 수 있어요.' % (term, josa, names)
    for t in TEMPLATES:
        refusal('S5 20개 밖 지표', t % term, message)
    for v in random.sample(VALUES, 2):
        refusal('S5 20개 밖 지표', '%s %s인 회사만 보여줘' % (term, v) if v[-1] != '는' else '%s %s 회사만 보여줘' % (term, v), message)

path = os.path.join(DATA, 'gen_s4_s5.jsonl')
with open(path, 'w', encoding='utf-8') as fp:
    for rec in out:
        fp.write(dump(rec) + '\n')
counts = {}
for rec in out:
    counts[rec['kind']] = counts.get(rec['kind'], 0) + 1
print(path, len(out), counts)
