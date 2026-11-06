"""병준의 merge_train_data.py 를 복사해 S1·S2 생성분(yappang/data/gen_s1_s2_pass.jsonl)을 입력에 추가한 버전.
팀원 데이터는 읽기만 하고, 결과는 yappang/train_model/data 에 저장한다. 원본 로직(평가 중복 제거, 입력 단위 분할, 시드 42)은 그대로.
실행: python -I scripts/merge_train_data.py
"""
import json
import random
from collections import Counter
from pathlib import Path

MEMBERS = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "data"

TRAIN_FILES = [
    "haechan/data/seed_1-7.jsonl",
    "haechan/data/seed_8-13.jsonl",
    "haechan/data/seed_14-20.jsonl",
    "hyeonkyeong/data/gen_s3.jsonl",
    "hyeonkyeong/data/gen_s4_s5.jsonl",
    "byungjun/data/S-4_gen_s6_s7.jsonl",
    "yappang/data/gen_s1_s2_pass.jsonl",
]
EVAL_FILES = [
    "hyeonkyeong/data/eval_1-7.jsonl",
    "hyeonkyeong/data/eval_8-13.jsonl",
    "hyeonkyeong/data/eval_14-20.jsonl",
]
VAL_RATIO = 0.05


def read_jsonl(path):
    with open(MEMBERS / path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def first_user(row):
    return row["messages"][1]["content"]


eval_texts = {first_user(r) for f in EVAL_FILES for r in read_jsonl(f)}

rows = []
removed = 0
for path in TRAIN_FILES:
    for i, row in enumerate(read_jsonl(path)):
        if first_user(row) in eval_texts:  # 평가 세트와 같은 질문은 뺀다
            removed += 1
            continue
        row["_source"] = path
        row["_line"] = i + 1
        rows.append(row)

random.seed(42)
# 같은 첫 질문(입력)은 한쪽에만 들어가도록 입력 단위로 묶어서 나눈다
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
    n_val = max(1, round(n_total * VAL_RATIO))
    count = 0
    for group in type_groups:
        if count < n_val:
            val += group
            count += len(group)
        else:
            train += group
random.shuffle(train)
random.shuffle(val)


def write(name, data, meta_only):
    with open(OUT / name, "w", encoding="utf-8", newline="\n") as f:
        for row in data:
            if meta_only:
                out = {k: v for k, v in row.items() if k != "messages"}
            else:
                out = {"messages": row["messages"]}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")


write("train.jsonl", train, False)
write("val.jsonl", val, False)
write("train_meta.jsonl", train, True)
write("val_meta.jsonl", val, True)

print("평가와 겹쳐 제외:", removed)
print("train", len(train), dict(Counter(r["type"] for r in train)))
print("val  ", len(val), dict(Counter(r["type"] for r in val)))
