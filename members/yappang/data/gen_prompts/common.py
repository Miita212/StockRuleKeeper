"""S-0/S-1 공용: 마스터(H1)·되묻기 선택지(H3) 읽기, 값을 말로 바꾸기."""
import glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.dirname(HERE)
DEFAULT_MASTER_DIR = os.path.normpath(os.path.join(DATA, '..', '..', 'byungjun', 'data'))
OP_WORD = {'<=': '이하', '>=': '이상', '<': '미만', '>': '초과'}


def load_master(d=DEFAULT_MASTER_DIR):
    m = {}
    for f in sorted(glob.glob(os.path.join(d, 'H1-*indicator_master*.json'))):
        for r in json.load(open(f, encoding='utf-8')):
            m[int(r['id'])] = r
    assert sorted(m) == list(range(1, 21)), '마스터에 없는 지표: %s' % sorted(set(range(1, 21)) - set(m))
    return m


def load_h3(d=DEFAULT_MASTER_DIR):
    h = {}
    for f in sorted(glob.glob(os.path.join(d, 'H3-[abc]_*.json'))):
        for r in json.load(open(f, encoding='utf-8')):
            h[int(r['id'])] = r
    assert sorted(h) == list(range(1, 21)), 'H3 선택지가 없는 지표'
    return h


def num(v):
    return str(int(v)) if float(v) == int(v) else str(v)


def value_phrases(v, unit):
    """정답 값(v, unit)을 문장에 넣을 때 허용하는 말 표현들. 조립 단계에서 문장에 이 중 하나가 있는지 확인한다."""
    n = num(v)
    if unit == '%':
        out = [n + '%', n + ' 퍼센트', n + '퍼센트']
        if v < 0:
            out += ['마이너스 %s%%' % num(-v), '마이너스 %s 퍼센트' % num(-v), '마이너스 %s퍼센트' % num(-v)]
        return out
    if unit == '배':
        return [n + '배']
    if unit == '년':
        return [n + '년']
    if unit == '억원':
        out = [n + '억', n + '억원', n + '억 원']
        if v >= 10000 and v % 10000 == 0:
            k = num(v // 10000)
            out += [k + '조', k + '조원', k + '조 원']
        if v >= 1000 and v % 1000 == 0:
            k = num(v // 1000)
            out += [k + '천억', k + '천억원', k + '천억 원']
        return out
    return [n + unit]


def direction_text(m):
    d = {'<=': '낮을수록 좋음', '>=': '높을수록 좋음', '<': '낮을수록 좋음', '>': '높을수록 좋음'}[m['operator']]
    return '%s (%s)' % (d, OP_WORD[m['operator']])


SAME_DIR = {'<=': ('<=', '<'), '<': ('<=', '<'), '>=': ('>=', '>'), '>': ('>=', '>')}


def same_dir_ops(m):
    """마스터 allowed_operators 안에서 기본 부등호와 같은 방향인 것들 (기본 부등호가 맨 앞)."""
    allowed = set(m.get('allowed_operators') or []) | {m['operator']}
    return [m['operator']] + [o for o in SAME_DIR[m['operator']] if o != m['operator'] and o in allowed]


# 기간(period_months)이 따로 필요한 지표. 마스터가 아니라 조건 값의 별도 필드로 다룬다 (H1-0 규칙 1, H3-0 T3).
PERIOD_IDS = {15}
PERIODS = [1, 3, 6, 12]
PERIOD_PHRASES = {1: ['1개월', '한 달', '한달'], 3: ['3개월', '세 달', '석 달'],
                  6: ['6개월', '반년', '여섯 달'], 12: ['12개월', '1년', '일 년', '열두 달']}
DEFAULT_SEED_DIR = os.path.normpath(os.path.join(DATA, '..', '..', 'haechan', 'data'))


def period_phrases(n):
    return PERIOD_PHRASES.get(n, ['%d개월' % n])


def load_period_template(seed_dir=DEFAULT_SEED_DIR):
    """시드(H4)에서 기간 되묻기 정답(PERIOD_MISSING) 하나를 가져온다. 문구·선택지를 지어내지 않고 팀 것을 그대로 쓴다."""
    for f in sorted(glob.glob(os.path.join(seed_dir, 'seed_*.jsonl'))):
        for ln in open(f, encoding='utf-8'):
            if not ln.strip():
                continue
            d = json.loads(ln)
            g = d['output'] if isinstance(d.get('output'), dict) else json.loads(d['messages'][-1]['content'])
            if g.get('reason') == 'PERIOD_MISSING' and 'known' not in g:
                return g
    raise FileNotFoundError('PERIOD_MISSING 시드를 찾지 못했어요: %s' % seed_dir)
