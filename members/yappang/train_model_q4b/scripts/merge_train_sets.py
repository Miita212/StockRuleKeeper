"""학습 데이터 병합 (yappang 버전). 기존 `merge_train_data.py`(병준 원본을 복사·수정한 것)와 같은 로직으로 다시 짠 파일이다.

하는 일
  1. 유형별 생성 파일(SEED, S1·S2, S3, S4·S5, S6·S7)을 읽는다. 팀원 파일은 읽기만 한다.
  2. 평가 세트(eval_*.jsonl)와 첫 질문이 같은 샘플은 학습에서 뺀다. 또 S1·S2(추가 파일)는 기존 데이터와 첫 질문이 같으면 뺀다
     (같은 입력에 정답이 달라지는 것을 막는 byungjun 최종 병합 코드의 규칙).
  3. 같은 첫 질문(입력)은 train 과 val 한쪽에만 들어가도록 입력 단위로 묶어서, 유형별로 val 비율(기본 5%)만큼 나눈다. 시드 42.
  4. train/val 과 메타(train_meta/val_meta)를 쓰고, 결과가 약속대로인지 검사해서 보여 준다.

수정 규칙(2026-11-08): 분할이 끝난 뒤 `yappang/data/scripts/data_fixes.py` 규칙을 적용한다(부등호 경계·조사 수정, 반전·깨진 문장 제외).
  분할을 먼저 하고 고치므로 train/val 배정은 병준 최종 병합과 같고, 결과 파일명에는 `_fixed`가 붙는다. 수정 없이 원본 결과가 필요하면 `--no-fix`.

기존 코드와 다른 점
  - 출력 폴더를 `--out`으로 고른다. 기본은 `train_model/outputs/merge_sets/`라서 학습에 쓰는 `train_model/data/`를 덮어쓰지 않는다.
  - val 비율·시드를 옵션으로 바꿀 수 있다(기본값은 기존과 같아서 같은 결과가 나온다).
  - 끝에 검사를 한다: 평가 문장 혼입 0건, train/val 첫 질문 겹침 0건, 메타 줄 수 일치. 어긋나면 종료 코드 1.
  - `--compare 폴더`로 다른 병합 결과(예: byungjun/finetune_merged)와 파일 해시를 비교할 수 있다.

실행 (members/yappang/train_model 에서)
  python -I -X utf8 scripts/merge_train_sets.py
  python -I -X utf8 scripts/merge_train_sets.py --compare ../../byungjun/finetune_merged
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEMBERS = HERE.parents[2]  # .../members

# (유형 설명, members/ 기준 경로). 경로는 각 작성자의 원본 파일이다.
TRAIN_FILES = [
    ("SEED 1-7", "haechan/data/seed_1-7.jsonl"),
    ("SEED 8-13", "haechan/data/seed_8-13.jsonl"),
    ("SEED 14-20", "haechan/data/seed_14-20.jsonl"),
    ("S3", "hyeonkyeong/data/gen_s3.jsonl"),
    ("S4·S5", "hyeonkyeong/data/gen_s4_s5.jsonl"),
    ("S6·S7", "byungjun/data/S-4_gen_s6_s7.jsonl"),
]
# 위 파일과 같은 첫 질문이 있으면 이 파일의 행을 뺀다(같은 입력에 정답이 달라지는 것을 막는다). byungjun 최종 병합 코드와 같은 규칙.
# (설명, 기록용 원본 경로, 실제로 읽을 ID 이름 복사본). byungjun 병합 코드는 원본 이름(gen_s1_s2_pass.jsonl)으로 읽으므로 원본은 남겨 둔다.
# 복사본(S-1_...)은 gitignore 대상이라 저장소에 없을 수 있다. 없으면 원본을 읽는다. 둘 다 있는데 내용이 다르면 멈춘다.
EXTRA_FILES = [
    ("S1·S2", "yappang/data/gen_s1_s2_pass.jsonl", "yappang/data/S-1_gen_s1_s2_pass.jsonl"),
]
EVAL_FILES = [
    "hyeonkyeong/data/eval_1-7.jsonl",
    "hyeonkyeong/data/eval_8-13.jsonl",
    "hyeonkyeong/data/eval_14-20.jsonl",
]
OUT_NAMES = ["train.jsonl", "val.jsonl", "train_meta.jsonl", "val_meta.jsonl"]
FIX_SCRIPTS = HERE.parents[1] / "data" / "scripts"  # data_fixes.py 가 있는 폴더


def out_names(fix):
    """결과 파일명. 수정 규칙을 적용하면 _fixed 를 붙여 원본 병합 결과와 구분한다."""
    return [n.replace(".jsonl", "_fixed.jsonl") for n in OUT_NAMES] if fix else list(OUT_NAMES)


def apply_fixes(rows):
    """분할된 행 목록에 수정 규칙을 적용한다. returns (행, 수정 건수, 제외 건수). 수정한 행은 메타에 _fix 가 남는다."""
    sys.path.insert(0, str(FIX_SCRIPTS))
    import data_fixes

    out, n_fix, n_drop = [], 0, 0
    for r in rows:
        nr, act, note = data_fixes.fix_row(r, r["type"])
        if act == "drop":
            n_drop += 1
            continue
        if act == "fix":
            nr = dict(nr)
            nr["_fix"] = note
            n_fix += 1
        out.append(nr)
    return out, n_fix, n_drop


def read_jsonl(rel):
    with open(MEMBERS / rel, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def first_user(row):
    return row["messages"][1]["content"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pick_source(item):
    """(설명, 원본 경로, 복사본 경로) 중 읽을 파일을 고른다. 둘 다 있으면 내용이 같은지 확인한다."""
    _, orig, copy = item
    has_o, has_c = (MEMBERS / orig).exists(), (MEMBERS / copy).exists()
    if has_o and has_c and sha(MEMBERS / orig) != sha(MEMBERS / copy):
        sys.exit(f"[중단] 원본과 ID 이름 복사본의 내용이 다르다: {orig} / {copy}\n"
                 "  byungjun 병합 코드는 원본을 읽으므로 두 파일을 같게 맞춘 뒤 다시 실행한다.")
    if has_c:
        return copy
    if has_o:
        print(f"  (복사본 없음, 원본 사용: {orig})")
        return orig
    sys.exit(f"[중단] 입력 파일이 없다: {orig}")


def load_rows(eval_texts):
    rows, removed, skipped = [], 0, 0
    seen = set()
    for extra, files in ((False, TRAIN_FILES), (True, EXTRA_FILES)):
        if extra:  # 기본 파일을 다 읽은 뒤의 첫 질문 목록. 추가 파일은 여기에 있는 질문을 건너뛴다
            seen = {first_user(r) for r in rows}
        for item in files:
            label, rel = item[0], item[1]  # rel = 메타에 기록하는 경로(원본)
            read_rel = pick_source(item) if extra else rel
            n_in = n_kept = 0
            for i, row in enumerate(read_jsonl(read_rel)):
                n_in += 1
                if first_user(row) in eval_texts:  # 평가 세트와 같은 질문은 뺀다
                    removed += 1
                    continue
                if extra:
                    if first_user(row) in seen:  # 기존 데이터·앞서 읽은 추가 행과 첫 질문이 같으면 뺀다
                        skipped += 1
                        continue
                    seen.add(first_user(row))
                row["_source"] = rel
                row["_line"] = i + 1
                rows.append(row)
                n_kept += 1
            print(f"  {label:10} 읽음 {n_in:5}  사용 {n_kept:5}  ({read_rel})")
    return rows, removed, skipped


def split(rows, val_ratio, seed):
    """입력 단위로 묶어 유형별로 val_ratio 만큼 val 로 보낸다. 로직·순서는 기존 merge_train_data.py 와 같다."""
    random.seed(seed)
    groups = {}
    for row in rows:
        groups.setdefault(first_user(row), []).append(row)
    by_type = {}
    for group in groups.values():
        by_type.setdefault(group[0]["type"], []).append(group)

    train, val = [], []
    for type_groups in by_type.values():
        random.shuffle(type_groups)
        n_total = sum(len(g) for g in type_groups)
        n_val = max(1, round(n_total * val_ratio))
        count = 0
        for group in type_groups:
            if count < n_val:
                val += group
                count += len(group)
            else:
                train += group
    random.shuffle(train)
    random.shuffle(val)
    return train, val


def write(out_dir, name, data, meta_only):
    with open(out_dir / name, "w", encoding="utf-8", newline="\n") as f:
        for row in data:
            if meta_only:
                out = {k: v for k, v in row.items() if k != "messages"}
            else:
                out = {"messages": row["messages"]}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


def check(train, val, eval_texts):
    """결과 검사. 문제 목록을 돌려준다(비어 있으면 통과)."""
    problems = []
    tf, vf = {first_user(r) for r in train}, {first_user(r) for r in val}
    if tf & vf:
        problems.append(f"train/val 첫 질문이 겹침: {len(tf & vf)}건")
    if (tf | vf) & eval_texts:
        problems.append(f"평가 문장이 학습에 섞임: {len((tf | vf) & eval_texts)}건")
    for r in train + val:
        roles = [m["role"] for m in r["messages"]]
        ok = roles[0] == "system" and roles[-1] == "assistant" and len(roles) >= 3
        if not (ok and all(x == ("user" if i % 2 == 0 else "assistant") for i, x in enumerate(roles[1:]))):
            problems.append(f"메시지 순서 이상: {r['_source']}:{r['_line']}")
            break
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE.parent / "outputs" / "merge_sets"))
    ap.add_argument("--val-ratio", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-fix", action="store_true", help="수정 규칙을 적용하지 않는다(원본 병합 결과, 파일명에 _fixed 없음)")
    ap.add_argument("--compare", default=None, help="이 폴더의 train/val/meta 와 해시를 비교")
    a = ap.parse_args()

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    eval_texts = {first_user(r) for rel in EVAL_FILES for r in read_jsonl(rel)}
    print(f"평가 문장 {len(eval_texts)}개 / 입력 파일:")
    rows, removed, skipped = load_rows(eval_texts)
    train, val = split(rows, a.val_ratio, a.seed)
    fix = not a.no_fix
    if fix:
        train, f1, d1 = apply_fixes(train)
        val, f2, d2 = apply_fixes(val)
        print(f"\n[수정 규칙] train 수정 {f1} / 제외 {d1}, val 수정 {f2} / 제외 {d2}")
    names = out_names(fix)

    write(out_dir, names[0], train, False)
    write(out_dir, names[1], val, False)
    write(out_dir, names[2], train, True)
    write(out_dir, names[3], val, True)

    print("\n평가와 겹쳐 제외:", removed)
    print("기존 데이터와 첫 질문이 같아 제외:", skipped)
    print("train", len(train), dict(sorted(Counter(r["type"] for r in train).items())))
    print("val  ", len(val), dict(sorted(Counter(r["type"] for r in val).items())))
    print("출력:", out_dir)

    problems = check(train, val, eval_texts)
    print("\n[검사]", "통과" if not problems else "문제 있음")
    for p in problems:
        print("  -", p)

    if a.compare:
        cmp_dir = Path(a.compare).resolve()
        print(f"\n[비교] {cmp_dir}")
        same = True
        for name in names:
            other = cmp_dir / name
            if not other.exists():
                print(f"  {name}: 상대 파일 없음")
                same = False
                continue
            eq = sha(out_dir / name) == sha(other)
            same &= eq
            print(f"  {name}: {'동일' if eq else '다름'}")
        print("  결과:", "완전히 같은 병합 결과" if same else "차이 있음")

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
