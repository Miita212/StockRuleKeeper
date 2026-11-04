"""S-2: S3 되묻기 대화 생성 (여러 턴) -> gen_s3.jsonl

대화 종류
  A 값 없음      : 말(사전) -> 기준값 되묻기 -> 선택(버튼 또는 직접 말함) -> 확정(20개 세트 + 말풍선)
  B 지표 모호    : 말(사전, 겹침 있음) -> 지표 되묻기 -> 지표 선택 -> 기준값 되묻기 -> 선택 -> 확정
  C 후보 5개 이상: 말 -> 영역 되묻기(AREA) -> 영역 선택 -> 지표 되묻기(INDICATOR) -> 지표 선택 -> 기준값 되묻기 -> 선택 -> 확정
  D 기간 없음    : 말(기간 수익률) -> 기간 되묻기 -> 기간 선택 -> 기준값 되묻기 -> 선택 -> 확정

문장은 yappang 동의어 사전(사람이 만든 표현)에서 가져오고, 정답은 마스터·H3 값으로 코드가 만든다. 외부 LLM은 쓰지 않는다.

사용: python -I -X utf8 gen_s3.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_common import *

random.seed(3)
PHRASES_PER_INDICATOR = 5
AMBIGUOUS_SAMPLES = 70

rows = [r for r in load_synonyms() if plain(r)]
out = []


def pick_option(i, level_index, mode):
    """사용자가 고르는 말. mode 0 = 버튼 글자 그대로, 1 = 값만 말함, 2 = 값 + 부등호를 말함"""
    o = H3[i]['options'][level_index]
    m = M[i]
    if mode == 0:
        return o, o['label']
    v = random.choice(spoken_variants(o['value'], m['unit']))
    if mode == 1:
        return o, '%s로 할게요' % v
    return o, '%s %s 할래요' % (v, OP_JOSA[m['operator']])


def record(kind, ids, turns):
    out.append(dict(type='S3', kind=kind, indicator_ids=ids,
                    messages=[msg('system', SYSTEM)] + [msg(r, c) for r, c in turns]))


# ---- A. 값 없음 ---------------------------------------------------------
by_id = {}
for r in rows:
    if not r['overlap'] and r['id'] != 15:
        by_id.setdefault(r['id'], []).append(r)
for i, lst in sorted(by_id.items()):
    for r in random.sample(lst, min(PHRASES_PER_INDICATOR, len(lst))):
        for level in range(3):
            o, said = pick_option(i, level, (level + i) % 3)
            record('A 값 없음', [i], [('user', r['text']), ('assistant', ask_value(i)), ('user', said),
                                    ('assistant', final_answer(i, o))])


# ---- B. 지표 모호 (후보 2~4개) -------------------------------------------
ambiguous = [r for r in rows if r['overlap'] and len(set([r['id']] + r['overlap'])) <= 4]
random.shuffle(ambiguous)
for n in range(AMBIGUOUS_SAMPLES):
    r = ambiguous[n % len(ambiguous)]
    ids = sorted(set([r['id']] + r['overlap']))
    i = random.choice([x for x in ids if x != 15] or ids)
    if i == 15:
        continue
    cands = [dict(id=x, label=M[x]['ui_name']) for x in ids]
    ask = dict(needs_clarification=True, reason='AMBIGUOUS_INDICATOR',
               message="'%s'은 여러 기준으로 볼 수 있어요. 어떤 걸로 볼까요?" % r['text'], candidates=cands)
    said_indicator = random.choice([M[i]['ui_name'], '%s로 볼게요' % M[i]['ui_name']])
    level = random.randrange(3)
    o, said = pick_option(i, level, random.randrange(3))
    record('B 지표 모호', ids, [('user', r['text']), ('assistant', ask), ('user', said_indicator),
                              ('assistant', ask_value(i)), ('user', said), ('assistant', final_answer(i, o))])


# ---- C. 후보 5개 이상: 2단계 되묻기 (영역 -> 지표) ------------------------
big = [r for r in rows if len(set([r['id']] + r['overlap'])) >= 5]
for r in big:
    ids = sorted(set([r['id']] + r['overlap']))
    areas = [a for a in AREAS if any(M[x]['area'] == a for x in ids)][:4]
    ask_area = dict(needs_clarification=True, reason='AMBIGUOUS_INDICATOR', stage='AREA',
                    message="'%s'은 여러 영역으로 볼 수 있어요. 어느 쪽으로 볼까요?" % r['text'],
                    candidates=[dict(area=a) for a in areas])
    for area in areas:
        in_area = [x for x in ids if M[x]['area'] == area][:4]
        turns = [('user', r['text']), ('assistant', ask_area), ('user', area)]
        if len(in_area) == 1:
            i = in_area[0]
        else:
            ask_ind = dict(needs_clarification=True, reason='AMBIGUOUS_INDICATOR', stage='INDICATOR',
                           message='%s에서는 어떤 기준으로 볼까요?' % area,
                           candidates=[dict(id=x, label=M[x]['ui_name']) for x in in_area])
            i = in_area[len(r['text']) % len(in_area)]
            turns += [('assistant', ask_ind), ('user', M[i]['ui_name'])]
        for level in range(3):
            o, said = pick_option(i, level, level)
            record('C 2단계', ids, turns + [('assistant', ask_value(i)), ('user', said), ('assistant', final_answer(i, o))])


# ---- D. 기간 없음 (기간 수익률) -------------------------------------------
for r in [r for r in rows if r['id'] == 15 and not r['overlap']]:
    for level in range(3):
        months = [1, 3, 6, 12][(level + len(r['text'])) % 4]
        said_period = random.choice(['최근 %d개월' % months, '%d개월로 할게요' % months])
        o, said = pick_option(15, level, level)
        record('D 기간 없음', [15], [('user', r['text']), ('assistant', ask_period()), ('user', said_period),
                                   ('assistant', ask_value(15, months)), ('user', said),
                                   ('assistant', final_answer(15, o, months))])


path = os.path.join(DATA, 'gen_s3.jsonl')
with open(path, 'w', encoding='utf-8') as fp:
    for rec in out:
        fp.write(dump(rec) + '\n')
counts = {}
for rec in out:
    counts[rec['kind']] = counts.get(rec['kind'], 0) + 1
print(path, len(out), counts)
