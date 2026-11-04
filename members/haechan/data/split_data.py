"""V-2 분할·중복 제거·평가 세트 격리: 학습/검증/평가를 나누고, 평가 문장이 학습에 섞이지 않게 한다.

사용법
    python -X utf8 split_data.py --pool seed_*.jsonl gen_*.jsonl --eval eval_*.jsonl --out split/ [--master-dir <마스터 폴더>]

입력
  --pool   학습 후보 파일들(시드, 자동 생성 결과 등). 앞에 쓴 파일이 우선한다(시드를 앞에 쓰면 시드가 남는다).
  --eval   사람이 쓴 평가 세트(H5, hyeonkyeong). 있으면 이 파일이 **그대로 평가(test) 세트**가 되고,
           후보 풀은 학습/검증으로만 나눈다. 없으면(골격 시험용) 풀을 학습:검증:평가 = 8:1:1 로 나누고 경고를 낸다.
  --ratio  학습:검증:평가 비율(기본 8:1:1). --eval 이 있으면 학습:검증 비율만 쓴다.
  --master-dir  주면 V-1(validate_data.py) 검사를 먼저 해서 실패한 샘플은 풀에서 뺀다.

규칙
  1. 같은 묶음(group)은 한쪽에만 간다. 묶음 = 시드와 그 시드에서 만든 변형(seed_id 또는 prompt_id 'S1B-<시드 id>').
  2. 같은 문장(공백·기호 무시)은 한 번만 남긴다. 같은 문장인데 정답이 다르면 뒤의 것을 버리고 '충돌'로 센다.
  3. 평가 세트와 같은 문장, 같은 seed_id, 거의 같은 문장(문자 2-gram 유사도 기준 이상)은 풀에서 뺀다.
  4. 분할 뒤 검사: 묶음·문장이 두 분할에 걸쳐 있으면 실패(종료 코드 1). 완료 기준 "평가 문장이 학습 데이터에 0건".
  5. 같은 --random-seed 면 같은 결과가 나온다. 샘플 유형(type)별로 나눠 검증·평가에도 각 유형이 들어가게 한다.

출력(--out): train.jsonl, valid.jsonl, test.jsonl, dropped.jsonl(버린 것과 이유), split_report.json
"""
import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_data as vd  # noqa: E402


# ---------------------------------------------------------------- 묶음·유사도
def group_key(rec):
    """같은 시드에서 나온 것끼리 같은 값. 시드 본문과 그 변형(prompt_id 'S1B-<시드 id>')이 한 묶음이다."""
    if rec.get("seed_id"):
        return str(rec["seed_id"])
    pid = rec.get("prompt_id")
    if pid:
        pid = str(pid)
        return pid[4:] if pid.startswith("S1B-") else pid
    return "txt:" + (vd.user_key(rec) or "")


def bigrams(text):
    t = vd.norm(text)
    return {t[i:i + 2] for i in range(len(t) - 1)} or {t}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


# ---------------------------------------------------------------- 정리 단계
def clean_pool(records, master=None):
    """형식 검사(V-1, 선택) → 중복·충돌 제거. (남은 샘플, 버린 목록)"""
    kept, dropped = [], []
    seen = {}  # 문장 → (정답 키)
    for rec in records:
        rec = vd.normalize_record(rec)
        key = vd.user_key(rec)
        if not key or "_parse_error" in rec:
            dropped.append({"reason": "invalid_format", "record": rec})
            continue
        if master is not None:
            errs = vd.validate_record(rec, master)
            if errs:
                dropped.append({"reason": "v1_" + errs[0][0].lower(), "detail": errs[0][1], "record": rec})
                continue
        ans = vd.answer_key(rec)
        if rec.get("type") in vd.TEXT_TYPES:
            # 설명 문장(S6~S8)은 같은 입력에 여러 문장이 정답일 수 있다(V-1 의 V6 과 같은 기준). 입력+정답이 같을 때만 중복.
            if (key, ans) in seen:
                dropped.append({"reason": "duplicate", "record": rec})
                continue
            seen[(key, ans)] = ans
        else:
            if key in seen:
                dropped.append({"reason": "duplicate" if seen[key] == ans else "conflict", "record": rec})
                continue
            seen[key] = ans
        kept.append(rec)
    return kept, dropped


def isolate_from_eval(pool, eval_records, near_threshold=0.85):
    """평가 세트와 겹치는 풀 샘플을 뺀다. (남은 샘플, 버린 목록)"""
    eval_texts = {vd.user_key(r) for r in map(vd.normalize_record, eval_records) if vd.user_key(r)}
    eval_seeds = {str(r["seed_id"]) for r in eval_records if r.get("seed_id")}
    eval_grams = [bigrams(t) for t in eval_texts]
    kept, dropped = [], []
    for rec in pool:
        key = vd.user_key(rec)
        if key in eval_texts:
            dropped.append({"reason": "eval_leak_exact", "record": rec})
        elif rec.get("seed_id") and str(rec["seed_id"]) in eval_seeds:
            dropped.append({"reason": "eval_leak_seed", "record": rec})
        elif near_threshold and any(jaccard(bigrams(key), g) >= near_threshold for g in eval_grams):
            dropped.append({"reason": "eval_leak_near", "record": rec})
        else:
            kept.append(rec)
    return kept, dropped


# ---------------------------------------------------------------- 분할
def split_pool(pool, train, valid, test, rnd):
    """묶음 단위로 유형별(stratified) 분할. {"train": [...], "valid": [...], "test": [...]}"""
    groups = defaultdict(list)
    for rec in pool:
        groups[group_key(rec)].append(rec)
    strata = defaultdict(list)  # 유형 → 묶음 목록 (묶음의 첫 샘플 유형 기준)
    for g, recs in groups.items():
        strata[recs[0].get("type", "?")].append(g)
    total = train + valid + test
    out = {"train": [], "valid": [], "test": []}
    for typ in sorted(strata):
        gs = sorted(strata[typ])
        rnd.shuffle(gs)
        n = len(gs)
        n_valid = round(n * valid / total) if valid else 0
        n_test = round(n * test / total) if test else 0
        if n >= 3:  # 너무 작으면 전부 학습. 3개 이상이면 검증·평가에도 최소 1개
            n_valid = max(n_valid, 1) if valid else 0
            n_test = max(n_test, 1) if test else 0
        if n_valid + n_test >= n:
            n_valid, n_test = (1 if valid and n > 1 else 0), 0
        names = ["valid"] * n_valid + ["test"] * n_test + ["train"] * (n - n_valid - n_test)
        for g, name in zip(gs, names):
            out[name].extend(groups[g])
    return out


def leak_check(splits):
    """분할끼리 겹치는 묶음·문장을 찾는다. 비어 있어야 통과."""
    problems = []
    names = list(splits)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ga, gb = {group_key(r) for r in splits[a]}, {group_key(r) for r in splits[b]}
            ta, tb = {vd.user_key(r) for r in splits[a]}, {vd.user_key(r) for r in splits[b]}
            if ga & gb:
                problems.append(f"{a}/{b} 묶음 겹침 {sorted(ga & gb)[:3]}")
            if ta & tb:
                problems.append(f"{a}/{b} 문장 겹침 {len(ta & tb)}개")
    return problems


def run(pool_records, eval_records, ratio=(8, 1, 1), master=None, random_seed=42, near_threshold=0.85):
    """전체 흐름. (splits, dropped, report)"""
    cleaned, dropped = clean_pool(pool_records, master)
    warnings = []
    if eval_records:
        eval_norm = [vd.normalize_record(r) for r in eval_records]
        cleaned, leaked = isolate_from_eval(cleaned, eval_norm, near_threshold)
        dropped += leaked
        splits = split_pool(cleaned, ratio[0], ratio[1], 0, random.Random(random_seed))
        splits["test"] = eval_norm
    else:
        warnings.append("평가 세트(--eval)가 없어 풀을 나눠 평가를 만들었어요. 골격 시험용이고, 실제 평가는 사람이 쓴 H5 를 써야 해요.")
        splits = split_pool(cleaned, *ratio, random.Random(random_seed))
    problems = leak_check(splits)
    report = {
        "입력": len(pool_records), "정리 후": len(cleaned),
        "분할": {k: len(v) for k, v in splits.items()},
        "버린 이유": dict(Counter(d["reason"] for d in dropped)),
        "유형별": {k: dict(Counter(r.get("type", "?") for r in v)) for k, v in splits.items()},
        "묶음 수": {k: len({group_key(r) for r in v}) for k, v in splits.items()},
        "겹침 검사": problems or "통과(분할 사이 겹침 0건)",
        "경고": warnings,
    }
    return splits, dropped, report


def write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="학습/검증/평가 분할 (V-2)")
    ap.add_argument("--pool", nargs="+", required=True)
    ap.add_argument("--eval", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--ratio", default="8:1:1")
    ap.add_argument("--master-dir")
    ap.add_argument("--random-seed", type=int, default=42)
    ap.add_argument("--near", type=float, default=0.85, help="평가 세트와 이 유사도 이상이면 풀에서 뺀다(0 이면 끔)")
    args = ap.parse_args(argv)

    ratio = tuple(int(x) for x in args.ratio.split(":"))
    master = vd.load_master(args.master_dir) if args.master_dir else None
    pool = [r for p in args.pool for r in vd.read_jsonl(p)]
    ev = [r for p in args.eval for r in vd.read_jsonl(p)]
    splits, dropped, report = run(pool, ev, ratio, master, args.random_seed, args.near)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in splits.items():
        write_jsonl(out / f"{name}.jsonl", rows)
    write_jsonl(out / "dropped.jsonl", dropped)
    (out / "split_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: report[k] for k in ("입력", "정리 후", "분할", "버린 이유", "겹침 검사")}, ensure_ascii=False, indent=2))
    for w in report["경고"]:
        print("[경고]", w)
    return 0 if not isinstance(report["겹침 검사"], list) else 1


if __name__ == "__main__":
    sys.exit(main())
