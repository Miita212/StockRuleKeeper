"""S-0 생성 입력 준비 v2: 동의어(H2) + 마스터(H1) + 되묻기 선택지(H3) → 생성용 프롬프트.

실행: python -I build_prompts.py [--master-dir 폴더] [--per-prompt 20] [--repeats 3] [--s2-combos 60] [--seeds 시드.jsonl ...]
출력: out/prompts_s1.jsonl, out/prompts_s2.jsonl, out/sample_for_review.md
각 프롬프트 줄에는 정답을 만들 때 쓸 메타(mode, indicator_ids, value 등)가 같이 들어 있다. 프롬프트만 만들고 생성은 하지 않는다.
D6 결론: 학습 데이터 생성은 로컬 모델로 한다 (외부 LLM으로 생성하지 않는다).
"""
import argparse, csv, glob, json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

AMBIG = ('모호', '포괄', '되묻기')


def fill(t, **kw):
    for k, v in kw.items():
        t = t.replace('{{%s}}' % k, str(v))
    assert '{{' not in t, t
    return t


def tpl(name):
    return open(os.path.join(HERE, 'templates', name), encoding='utf-8').read()


def load_syn():
    rows = []
    for fn in sorted(glob.glob(os.path.join(DATA, 'synonyms_*.csv'))):
        with open(fn, encoding='utf-8-sig', newline='') as f:
            rows += list(csv.DictReader(f))
    return rows


def ids_of(s):
    return [int(x) for x in s.split(',') if x.strip()]


def is_clear(r):
    if '반대 방향' in r['메모']:
        return False
    return not (r['겹침_지표번호'].strip() and any(w in r['메모'] for w in AMBIG))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master-dir', default=DEFAULT_MASTER_DIR)
    ap.add_argument('--per-prompt', type=int, default=20)
    ap.add_argument('--value-per-prompt', type=int, default=10)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--s2-combos', type=int, default=60)
    ap.add_argument('--s2-per-prompt', type=int, default=10)
    ap.add_argument('--seeds', nargs='*', default=[])
    ap.add_argument('--random-seed', type=int, default=42)
    a = ap.parse_args()
    rnd = random.Random(a.random_seed)
    M, H3, syn = load_master(a.master_dir), load_h3(a.master_dir), load_syn()
    ref = {i['id']: i for i in json.load(open(os.path.join(HERE, 'indicators_ref.json'), encoding='utf-8'))}
    by = {}
    for r in syn:
        by.setdefault(int(r['지표번호']), []).append(r)

    s1, s2 = [], []
    for i, m in M.items():
        clear = [r for r in by[i] if is_clear(r)]
        assert len(clear) >= 6, (i, len(clear))
        base = dict(NAME=m['ui_name'], AREA=m['area'], ID=i, EXAMPLE=ref[i]['example'],
                    DEFINITION=m['definition'], DIRECTION=direction_text(m))

        def expr():
            rows = clear[:]
            rnd.shuffle(rows)
            return '\n'.join('- %s (%s)' % (r['표현'], r['유형']) for r in rows)

        # S1-A 값 없음: 정답 = 기준값을 되묻는 VALUE_MISSING (H3-0 T1)
        for k in range(a.repeats):
            s1.append(dict(prompt_id='S1A-%02d-%d' % (i, k + 1), template='s1_from_expressions', mode='no_value',
                           indicator_ids=[i], n=a.per_prompt,
                           prompt=fill(tpl('s1_from_expressions.txt'), N=a.per_prompt, EXPRESSIONS=expr(),
                                       VALUE_RULE='숫자 기준(예: 100%, 3년)은 넣지 않는다. 말만으로 쓴다.', OP_FIELD='', **base)))
        # S1-V 값 있음: 엄격/보통/느슨 값을 문장에 넣는다. 정답 = 그 값으로 확정 (T4)
        for opt in H3[i]['options']:
            ph = value_phrases(opt['value'], m['unit'])
            ops = same_dir_ops(m)
            opw = {OP_WORD[o]: o for o in ops}  # 예: {'이하': '<=', '미만': '<'}
            rule = ('문장에 기준 숫자를 반드시 넣는다: %s 중 하나를 그대로 쓴다. 숫자 뒤에 %s 중 하나를 문장에 쓰고, 쓴 말을 op_word 에 적는다. 다른 숫자는 넣지 않는다.'
                    % (' / '.join('"%s"' % p for p in ph), ' / '.join('"%s"' % w for w in opw)))
            s1.append(dict(prompt_id='S1V-%02d-%s' % (i, opt['level']), template='s1_from_expressions', mode='with_value',
                           indicator_ids=[i], n=a.value_per_prompt, value=opt['value'], level=opt['level'],
                           value_phrases=ph, op_words=opw,
                           prompt=fill(tpl('s1_from_expressions.txt'), N=a.value_per_prompt, EXPRESSIONS=expr(),
                                       VALUE_RULE=rule, OP_FIELD=', "op_word": "%s"' % '|'.join(opw), **base)))
    # S1-B 시드 (H4가 있을 때)
    skipped = 0
    for fn in a.seeds:
        for ln, line in enumerate(open(fn, encoding='utf-8')):
            if not line.strip():
                continue
            d = json.loads(line)
            text = d.get('text') or d.get('input') or d.get('user_text')
            ids = d.get('indicator_ids') or d.get('anchors') or []
            if not text or not ids:
                skipped += 1
                continue
            sid = str(d.get('id', '%s:%d' % (os.path.basename(fn), ln + 1)))
            s1.append(dict(prompt_id='S1B-' + sid, template='s1_from_seed', mode='seed', indicator_ids=ids,
                           n=a.per_prompt, seed_gold=d.get('output'),
                           prompt=fill(tpl('s1_from_seed.txt'), SEED_TEXT=text, SEED_IDS=json.dumps(ids), SEED_ID=sid, N=a.per_prompt)))
    # S2-A 복수 지표: 보통(default) 값을 문장에 넣는다
    combos, tries = set(), 0
    while len(combos) < a.s2_combos and tries < 10000:
        tries += 1
        k = rnd.choice([2, 2, 3])
        c = tuple(sorted(rnd.sample(list(M), k)))
        if len({M[x]['area'] for x in c}) == k:
            combos.add(c)
    for c in sorted(combos):
        vals, vlines, ex = {}, [], []
        for x in c:
            v = M[x]['default']  # 마스터 default를 기준으로 삼는다 (H3 보통 값과 다르면 아래 경고)
            if H3[x]['options'][1]['value'] != v and H3[x].get('normal_equals_default', True):
                print('[경고] 지표 %d: 마스터 default=%s, H3 보통=%s (H3-0 정책은 둘이 같아야 함)' % (x, v, H3[x]['options'][1]['value']), file=sys.stderr)
            ph = value_phrases(v, M[x]['unit'])
            vals[x] = dict(value=v, phrases=ph)
            vlines.append('- %d. %s: %s %s (쓸 말: %s)' % (x, M[x]['ui_name'], num(v) + M[x]['unit'], OP_WORD[M[x]['operator']],
                                                         ' / '.join('"%s"' % p for p in ph)))
            ex.append('[%s]\n%s' % (M[x]['ui_name'], '\n'.join('- ' + r['표현'] for r in rnd.sample([q for q in by[x] if is_clear(q)], 5))))
        indl = '\n'.join('- %d. %s (%s)' % (x, M[x]['ui_name'], M[x]['area']) for x in c)
        s2.append(dict(prompt_id='S2A-' + '_'.join('%02d' % x for x in c), template='s2_multi', mode='multi_value',
                       indicator_ids=list(c), n=a.s2_per_prompt, values={str(k): v for k, v in vals.items()},
                       prompt=fill(tpl('s2_multi.txt'), COUNT=len(c), INDICATORS=indl, VALUE_LINES='\n'.join(vlines),
                                   EXPRESSIONS='\n'.join(ex), N=a.s2_per_prompt, IDS=json.dumps(list(c)))))
    # S2-B 모호한 표현: 정답 = 지표를 되묻는 AMBIGUOUS_INDICATOR (T2)
    nb = 0
    for r in syn:
        ov = ids_of(r['겹침_지표번호'])
        if ov and any(w in r['메모'] for w in AMBIG):
            nb += 1
            cand = sorted({int(r['지표번호'])} | set(ov))
            s2.append(dict(prompt_id='S2B-%02d-%02d' % (int(r['지표번호']), nb), template='s2_ambiguous', mode='ambiguous',
                           indicator_ids=cand, n=a.s2_per_prompt, expression=r['표현'],
                           prompt=fill(tpl('s2_ambiguous.txt'), EXPRESSION=r['표현'],
                                       CANDIDATES=', '.join('%d.%s' % (x, M[x]['ui_name']) for x in cand),
                                       CAND_IDS=json.dumps(cand), N=a.s2_per_prompt)))
    out = os.path.join(HERE, 'out')
    os.makedirs(out, exist_ok=True)
    for name, lst in (('prompts_s1.jsonl', s1), ('prompts_s2.jsonl', s2)):
        with open(os.path.join(out, name), 'w', encoding='utf-8') as f:
            for p in lst:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')
    pick = [p for p in s1 if p['mode'] == 'no_value'][:1] + [p for p in s1 if p['mode'] == 'with_value'][3:5] + \
           [p for p in s2 if p['mode'] == 'multi_value'][:2] + [p for p in s2 if p['mode'] == 'ambiguous'][:2]
    with open(os.path.join(out, 'sample_for_review.md'), 'w', encoding='utf-8') as f:
        f.write('# 프롬프트 사람 확인용 샘플 (%d개)\n\n' % len(pick))
        for p in pick:
            f.write('## %s (%s)\n\n```\n%s\n```\n\n' % (p['prompt_id'], p['mode'], p['prompt']))
    cnt = {}
    for p in s1 + s2:
        cnt[p['mode']] = cnt.get(p['mode'], 0) + p['n']
    print('S1 %d / S2 %d / skipped seeds %d / expected sentences by mode: %s' % (len(s1), len(s2), skipped, cnt))


main()
