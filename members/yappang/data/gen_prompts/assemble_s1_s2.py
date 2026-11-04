"""S-1 조립: 로컬 모델이 만든 문장(raw)을 정답 JSON과 묶어 학습 샘플(jsonl)로 만든다.

입력(raw): 한 줄 = {"prompt_id": "S1V-01-엄격", "response": "모델이 출력한 원문(JSONL 여러 줄)"}
출력: gen_s1_s2.jsonl (messages 형식) + rejects.jsonl (버린 것과 이유)

사용:
  python -I assemble_s1_s2.py --raw raw_outputs.jsonl --out ../gen_s1_s2.jsonl --rejects out/rejects.jsonl
그 다음 V-1 검증: python -I <haechan의 validate_data.py> --master-dir <byungjun 마스터 폴더> --input gen_s1_s2.jsonl

정답은 모델이 아니라 이 코드가 마스터(H1)와 선택지(H3)로 만든다. 모델이 낸 값·지표는 믿지 않고 프롬프트 메타와 대조만 한다.
이 스크립트는 생성을 하지 않는다 (D6: 학습 데이터 생성은 로컬 모델).
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

STYLES = {'존댓말', '반말', '줄임말', '오타', '영어약어'}
SYSTEM = ('너는 투자 원칙 점검 앱의 도우미야. 사용자의 말을 지표 20개 기준 JSON으로 바꿔. '
          'JSON만 출력하고, 종목 추천이나 수익 예측은 하지 않아.')  # [제안] 팀 합의 전 임시 문구
MAX_CANDIDATES = 4  # H3-0: 후보 지표는 2~4개
NUM = re.compile(r'\d')


def gold_full(M, anchors, ops=None):
    """E06 형식: 말한 지표는 source=user, 나머지는 마스터 기본값 source=default. anchors = {id: value}, ops = {id: 부등호}"""
    ops = ops or {}
    inds = []
    for i in range(1, 21):
        m = M[i]
        if i in anchors:
            inds.append(dict(id=i, operator=ops.get(i, m['operator']), value=anchors[i], unit=m['unit'], source='user'))
        else:
            inds.append(dict(id=i, operator=m['operator'], value=m['default'], unit=m['unit'], source='default'))
    return dict(indicators=inds, anchors=sorted(anchors))


def strip_phrases(text, phrases):
    for p in sorted(phrases, key=len, reverse=True):
        text = text.replace(p, ' ')
    return text


def parse_lines(resp):
    out, bad = [], 0
    for ln in str(resp).splitlines():
        ln = ln.strip()
        if not ln or ln.startswith('```'):
            continue
        try:
            d = json.loads(ln)
            if isinstance(d, dict) and isinstance(d.get('text'), str) and d['text'].strip():
                out.append(d)
            else:
                bad += 1
        except ValueError:
            bad += 1
    return out, bad


def build(meta, d, M, H3):
    """(정답 dict, 타입) 또는 (None, 거절 이유)"""
    text, mode, ids = d['text'].strip(), meta['mode'], meta['indicator_ids']
    if d.get('style') not in STYLES:
        return None, 'style 값 이상: %r' % d.get('style')
    if mode in ('no_value', 'ambiguous'):
        if NUM.search(text):
            return None, '숫자가 들어 있음 (값 없는 문장이어야 함)'
    if mode == 'no_value':
        if d.get('indicator_ids') != ids:
            return None, 'indicator_ids 가 프롬프트와 다름'
        i = ids[0]
        h = H3[i]
        gold = dict(needs_clarification=True, reason='VALUE_MISSING', indicator_id=i,
                    message=h.get('clarify_message') or '%s 기준을 정해 볼게요. 어느 정도까지 괜찮을까요?' % M[i]['ui_name'],  # H3 지표별 문구, 없으면 임시 문구
                    options=[dict(level=o['level'], label=o['label'], value=o['value']) for o in h['options']])
        return (gold, 'S1'), None
    if mode == 'with_value':
        if d.get('indicator_ids') != ids:
            return None, 'indicator_ids 가 프롬프트와 다름'
        if not any(p in text for p in meta['value_phrases']):
            return None, '기준 숫자 표현이 문장에 없음'
        if NUM.search(strip_phrases(text, meta['value_phrases'])):
            return None, '기준 말고 다른 숫자가 있음'
        w = d.get('op_word')
        if w not in meta['op_words']:
            return None, 'op_word %r 가 허용 목록 %s 에 없음' % (w, list(meta['op_words']))
        if w not in text:
            return None, 'op_word %r 가 문장에 없음' % w
        other = [x for x in meta['op_words'] if x != w]
        if any(x in text for x in other):
            return None, '문장에 부등호 말이 두 가지 섞임'
        return (gold_full(M, {ids[0]: meta['value']}, {ids[0]: meta['op_words'][w]}), 'S1'), None
    if mode == 'multi_value':
        if sorted(d.get('indicator_ids', [])) != sorted(ids):
            return None, 'indicator_ids 가 프롬프트와 다름'
        allp = []
        for k, v in meta['values'].items():
            if not any(p in text for p in v['phrases']):
                return None, '지표 %s 의 기준 숫자가 문장에 없음' % k
            allp += v['phrases']
        if NUM.search(strip_phrases(text, allp)):
            return None, '기준 말고 다른 숫자가 있음'
        return (gold_full(M, {int(k): v['value'] for k, v in meta['values'].items()}), 'S2'), None
    if mode == 'ambiguous':
        if d.get('needs_clarification') is not True or sorted(d.get('candidate_ids', [])) != sorted(ids):
            return None, 'candidate_ids/needs_clarification 이 프롬프트와 다름'
        if len(ids) > MAX_CANDIDATES:
            return None, '후보 지표가 %d개: 2단계 되묻기 대화(S3)로 만들어야 함. 검증 코드도 아직 stage 미지원' % len(ids)
        gold = dict(needs_clarification=True, reason='AMBIGUOUS_INDICATOR',
                    message='어떤 기준으로 볼까요? 아래에서 골라 주세요.',  # [제안] 임시 문구
                    candidates=[dict(id=i, name=M[i]['ui_name']) for i in ids])
        return (gold, 'S2'), None
    if mode == 'seed':
        if meta.get('seed_gold') is None:
            return None, '시드 정답(output)이 없음'
        return (meta['seed_gold'], 'S1'), None
    return None, '알 수 없는 mode %r' % mode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--rejects', default=os.path.join(HERE, 'out', 'rejects.jsonl'))
    ap.add_argument('--master-dir', default=DEFAULT_MASTER_DIR)
    a = ap.parse_args()
    M, H3 = load_master(a.master_dir), load_h3(a.master_dir)
    meta = {}
    for fn in ('prompts_s1.jsonl', 'prompts_s2.jsonl'):
        for ln in open(os.path.join(HERE, 'out', fn), encoding='utf-8'):
            p = json.loads(ln)
            meta[p['prompt_id']] = p
    seen, kept, rej, badlines = set(), [], [], 0
    for ln in open(a.raw, encoding='utf-8'):
        if not ln.strip():
            continue
        r = json.loads(ln)
        pm = meta.get(r['prompt_id'])
        if pm is None:
            rej.append(dict(prompt_id=r['prompt_id'], reason='알 수 없는 prompt_id'))
            continue
        items, bad = parse_lines(r['response'])
        badlines += bad
        for d in items:
            key = re.sub(r'\s+', '', d['text'])
            if key in seen:
                rej.append(dict(prompt_id=r['prompt_id'], text=d['text'], reason='중복 문장'))
                continue
            res, why = build(pm, d, M, H3)
            if res is None:
                rej.append(dict(prompt_id=r['prompt_id'], text=d['text'], reason=why))
                continue
            gold, typ = res
            seen.add(key)
            kept.append(dict(type=typ, indicator_ids=pm['indicator_ids'], prompt_id=r['prompt_id'], style=d['style'],
                             messages=[dict(role='system', content=SYSTEM), dict(role='user', content=d['text'].strip()),
                                       dict(role='assistant', content=json.dumps(gold, ensure_ascii=False))]))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        for k in kept:
            f.write(json.dumps(k, ensure_ascii=False) + '\n')
    os.makedirs(os.path.dirname(os.path.abspath(a.rejects)), exist_ok=True)
    with open(a.rejects, 'w', encoding='utf-8') as f:
        for k in rej:
            f.write(json.dumps(k, ensure_ascii=False) + '\n')
    print('kept %d / rejected %d / unparsable lines %d' % (len(kept), len(rej), badlines))


main()
