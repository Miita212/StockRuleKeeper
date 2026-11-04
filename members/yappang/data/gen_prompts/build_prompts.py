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


def parse_seed(d, default_id):
    """시드 한 줄을 공통 모양으로. 지표가 없는 시드(거절)와 기타는 skip 사유를 달아 건너뛴다."""
    if 'messages' in d:  # haechan 형식
        msgs = d['messages']
        user = [m['content'] for m in msgs if m['role'] == 'user']
        asst = [m['content'] for m in msgs if m['role'] == 'assistant']
        system = next((m['content'] for m in msgs if m['role'] == 'system'), '')
        text, gold_text = (user[0] if user else None), (asst[0] if asst else None)
    else:
        text, gold_text, system = d.get('text') or d.get('input') or d.get('user_text'), None, ''
        if isinstance(d.get('output'), (dict, str)):
            gold_text = d['output'] if isinstance(d['output'], str) else json.dumps(d['output'], ensure_ascii=False)
    try:
        gold = json.loads(gold_text) if gold_text else None
    except ValueError:
        gold = None
    ids = d.get('indicator_ids') or d.get('anchors') or []
    sid = str(d.get('seed_id') or d.get('id') or default_id)
    base = dict(seed_id=sid, text=text, ids=ids, gold=gold, gold_text=gold_text, system=system, kind=d.get('kind', ''), skip=None)
    if not text or gold is None:
        base['skip'] = '문장 또는 정답 없음'
    elif gold.get('refusal'):
        base['refusal'] = True  # 거절 시드: 지표 없이 거절 변형 프롬프트를 만든다
        base['note'] = d.get('note', '')
    elif not ids:
        base['skip'] = '지표 없음'
    elif len(ids) > 1 and gold.get('needs_clarification') and len(gold.get('candidates', [])) > 4:
        base['skip'] = '후보 5개 이상'
    return base


def user_inds(g):
    """정답에서 사용자가 말한 지표만. 20개 세트 정답은 source=user 또는 anchors 에 있는 것만 본다 (나머지는 기본값)."""
    inds = g.get('indicators', [])
    anchors = set(g.get('anchors', []))
    if anchors or any(e.get('source') == 'user' for e in inds):
        return [e for e in inds if e.get('id') in anchors or e.get('source') == 'user']
    return inds


REASON_TEXT = {'VALUE_MISSING': '지표는 정해졌지만 기준값(숫자)이 없다',
               'AMBIGUOUS_INDICATOR': '말이 여러 지표로 갈려서 어느 지표인지 정해지지 않는다',
               'PERIOD_MISSING': '기간이 빠져 있다'}


def meaning(sd, M):
    g = sd['gold']
    if g.get('needs_clarification'):
        names = ', '.join('%d.%s' % (i, M[i]['ui_name']) for i in sd['ids'])
        extra = ' 후보 지표: ' + names if g.get('reason') == 'AMBIGUOUS_INDICATOR' else ' 지표: ' + names
        return ('이 문장은 앱이 사용자에게 되물어야 하는 문장이다: %s.%s\n'
                '변형도 같은 이유로 되물어야 하는 문장이어야 한다. 숫자, 기간, 지표를 스스로 정해 주면 안 된다.'
                % (REASON_TEXT.get(g.get('reason'), g.get('reason')), extra))
    lines = []
    for e in user_inds(g):
        i = e['id']
        t = '- %d.%s: %s %s %s' % (i, M[i]['ui_name'], OP_WORD.get(e['operator'], e['operator']) + '(%s)' % e['operator'],
                                   num(e['value']) + e['unit'] if 'value' in e else '', '')
        if 'value' in e:
            t += ' (쓸 말: %s)' % ' / '.join('"%s"' % p for p in value_phrases(e['value'], e['unit']))
        if e.get('period_months'):
            t += ' 기간 %d개월 (쓸 말: %s)' % (e['period_months'], ' / '.join('"%s"' % p for p in period_phrases(e['period_months'])))
        lines.append(t.rstrip())
    return '문장은 아래 조건을 모두, 숫자·단위·부등호 뜻 그대로 담아야 한다.\n' + '\n'.join(lines)


def refusal_reason(note):
    """시드 note 에서 거절 종류를 사람 말로. (note 는 H4 작성자가 적은 짧은 메모)"""
    if '20개 밖' in note:
        return '앱이 지원하지 않는 지표(20개 목록에 없는 지표)를 요구하는 말이다'
    if '추천' in note:
        return '특정 종목을 사도 되는지, 추천해 달라는 말이다'
    if '예측' in note:
        return '앞으로 오를지 내릴지 맞혀 달라는 예측 요청이다'
    return '앱이 하지 않는 일을 요구하는 말이다 (%s)' % note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--master-dir', default=DEFAULT_MASTER_DIR)
    ap.add_argument('--per-prompt', type=int, default=20)
    ap.add_argument('--value-per-prompt', type=int, default=10)
    ap.add_argument('--repeats', type=int, default=3)
    ap.add_argument('--s2-combos', type=int, default=60)
    ap.add_argument('--s2-per-prompt', type=int, default=10)
    ap.add_argument('--seeds', nargs='*', default=[])
    ap.add_argument('--seed-n', type=int, default=10)
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
        # 기간이 필요한 지표(15)는 기간이 없으면 값보다 기간을 먼저 되묻는다 (T3): 정답 = PERIOD_MISSING
        period_missing = i in PERIOD_IDS
        nv_rule = '숫자 기준(예: 100%, 3년)은 넣지 않는다. 말만으로 쓴다.'
        if period_missing:
            nv_rule = '숫자 기준(예: 10%)과 기간(예: 3개월, 한 달, 올해)은 넣지 않는다. 말만으로 쓴다. 기간이 없는 문장이어야 한다.'
        for k in range(a.repeats):
            s1.append(dict(prompt_id='S1A-%02d-%d' % (i, k + 1), template='s1_from_expressions', mode='no_value',
                           indicator_ids=[i], n=a.per_prompt, period_missing=period_missing,
                           prompt=fill(tpl('s1_from_expressions.txt'), N=a.per_prompt, EXPRESSIONS=expr(),
                                       VALUE_RULE=nv_rule, OP_FIELD='', **base)))
        # S1-V 값 있음: 엄격/보통/느슨 값을 문장에 넣는다. 정답 = 그 값으로 확정 (T4)
        # 기간이 필요한 지표는 기간(1/3/6/12개월)도 넣는다. 정답에 period_months 가 붙는다.
        for opt in H3[i]['options']:
            ph = value_phrases(opt['value'], m['unit'])
            ops = same_dir_ops(m)
            opw = {OP_WORD[o]: o for o in ops}  # 예: {'이하': '<=', '미만': '<'}
            for pm in (PERIODS if period_missing else [None]):
                rule = ('문장에 기준 숫자를 반드시 넣는다: %s 중 하나를 그대로 쓴다. 숫자 뒤에 %s 중 하나를 문장에 쓰고, 쓴 말을 op_word 에 적는다. 다른 숫자는 넣지 않는다.'
                        % (' / '.join('"%s"' % p for p in ph), ' / '.join('"%s"' % w for w in opw)))
                extra = {}
                pid = 'S1V-%02d-%s' % (i, opt['level'])
                n_here = a.value_per_prompt
                if pm:
                    pph = period_phrases(pm)
                    rule += ' 기간도 반드시 넣는다: %s 중 하나를 그대로 쓴다.' % ' / '.join('"%s"' % p for p in pph)
                    extra = dict(period_months=pm, period_phrases=pph)
                    pid += '-%dm' % pm
                    n_here = max(3, a.value_per_prompt // 2)
                s1.append(dict(prompt_id=pid, template='s1_from_expressions', mode='with_value',
                               indicator_ids=[i], n=n_here, value=opt['value'], level=opt['level'],
                               value_phrases=ph, op_words=opw, **extra,
                               prompt=fill(tpl('s1_from_expressions.txt'), N=n_here, EXPRESSIONS=expr(),
                                           VALUE_RULE=rule, OP_FIELD=', "op_word": "%s"' % '|'.join(opw), **base)))
    # S1-B 시드 변형 (H4). 시드 형식: haechan 의 messages 형태(SEED) 또는 {text, indicator_ids}
    skipped = {}
    for fn in a.seeds:
        for ln, line in enumerate(open(fn, encoding='utf-8')):
            if not line.strip():
                continue
            sd = parse_seed(json.loads(line), '%s:%d' % (os.path.basename(fn), ln + 1))
            if sd['skip']:
                skipped[sd['skip']] = skipped.get(sd['skip'], 0) + 1
                continue
            if sd.get('refusal'):  # 거절 시드: 같은 거절 이유로 말만 바꾼다. 정답 = 시드의 거절 JSON
                s1.append(dict(prompt_id='S5R-' + sd['seed_id'], template='s5_refusal_seed', mode='refusal_seed',
                               indicator_ids=[], n=a.seed_n, seed_id=sd['seed_id'], seed_kind=sd['kind'],
                               seed_system=sd['system'], seed_gold_text=sd['gold_text'], seed_text=sd['text'],
                               seed_note=sd['note'], required_groups=[],
                               prompt=fill(tpl('s5_refusal_seed.txt'), SEED_TEXT=sd['text'], SEED_ID=sd['seed_id'],
                                           REASON=refusal_reason(sd['note']), MESSAGE=sd['gold']['message'],
                                           INDICATORS=', '.join(M[x]['ui_name'] for x in sorted(M)), N=a.seed_n)))
                continue
            groups = []  # 변형 문장에 반드시 있어야 하는 말 (지표마다 하나 이상)
            for e in user_inds(sd['gold'] or {}):
                if 'value' in e:
                    groups.append(value_phrases(e['value'], e['unit']))
                if e.get('period_months'):
                    groups.append(period_phrases(e['period_months']))
            s1.append(dict(prompt_id='S1B-' + sd['seed_id'], template='s1_from_seed', mode='seed',
                           indicator_ids=sd['ids'], n=a.seed_n, seed_id=sd['seed_id'], seed_kind=sd['kind'],
                           seed_system=sd['system'], seed_gold_text=sd['gold_text'], seed_text=sd['text'],
                           required_groups=groups,
                           prompt=fill(tpl('s1_from_seed.txt'), SEED_TEXT=sd['text'], SEED_ID=sd['seed_id'],
                                       MEANING=meaning(sd, M), N=a.seed_n)))
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
            vline = '- %d. %s: %s %s (쓸 말: %s)' % (x, M[x]['ui_name'], num(v) + M[x]['unit'], OP_WORD[M[x]['operator']],
                                                    ' / '.join('"%s"' % p for p in ph))
            if x in PERIOD_IDS:  # 기간이 필요한 지표: 기간도 문장에 넣고 정답에 period_months 를 붙인다
                pm = rnd.choice(PERIODS)
                vals[x].update(period_months=pm, period_phrases=period_phrases(pm))
                vline += ' 기간 %d개월 (쓸 말: %s)' % (pm, ' / '.join('"%s"' % p for p in period_phrases(pm)))
            vlines.append(vline)
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
    print('S1 %d / S2 %d / skipped seeds %s / expected sentences by mode: %s' % (len(s1), len(s2), skipped, cnt))


main()
