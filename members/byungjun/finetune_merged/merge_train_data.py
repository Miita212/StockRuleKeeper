"""팀원 학습 데이터를 읽기만 하고 합쳐 byungjun/finetune_merged 에 저장한다."""
import json
import random
from collections import Counter
from pathlib import Path

MEMBERS = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

TRAIN_FILES = [
    "haechan/data/seed_1-7.jsonl",
    "haechan/data/seed_8-13.jsonl",
    "haechan/data/seed_14-20.jsonl",
    "hyeonkyeong/data/gen_s3.jsonl",
    "hyeonkyeong/data/gen_s4_s5.jsonl",
    "byungjun/data/S-4_gen_s6_s7.jsonl",
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
by_type = {}
for row in rows:
    by_type.setdefault(row["type"], []).append(row)

train, val = [], []
for type_rows in by_type.values():
    random.shuffle(type_rows)
    n_val = max(1, round(len(type_rows) * VAL_RATIO))
    val += type_rows[:n_val]
    train += type_rows[n_val:]
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
