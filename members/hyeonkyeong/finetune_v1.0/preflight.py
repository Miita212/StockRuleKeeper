"""학습 전 점검: 토큰 길이(잘림 0건인지)와 마스크(assistant 답변만 학습되는지).

사용법:
  python preflight.py                          # 서버: models/Qwen3-8B 토크나이저
  python preflight.py --model Qwen/Qwen3-1.7B  # 노트북에서 미리 (Qwen3 계열은 토크나이저·템플릿이 같음)
"""
import argparse
from collections import defaultdict

from transformers import AutoTokenizer

from common import build_examples, load_jsonl

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="models/Qwen3-8B")
parser.add_argument("--max_len", type=int, default=2048)
args = parser.parse_args()

tokenizer = AutoTokenizer.from_pretrained(args.model)

# 1) 토큰 길이 (턴별 분할 후 샘플 기준) ----------------------------------------------
print("===== 1. 토큰 길이 (max_len =", args.max_len, ") =====")
for split in ["train", "val"]:
    rows = load_jsonl(f"data/{split}.jsonl")
    metas = load_jsonl(f"data/{split}_meta.jsonl")
    lengths = defaultdict(list)
    for row, meta in zip(rows, metas):
        for ex in build_examples(tokenizer, row["messages"]):
            lengths[meta["type"]].append(len(ex["input_ids"]))

    all_lengths = [n for ns in lengths.values() for n in ns]
    over = sum(n > args.max_len for n in all_lengths)
    print(f"[{split}] 대화 {len(rows)}개 → 샘플 {len(all_lengths)}개  최대 {max(all_lengths)}  "
          f"평균 {sum(all_lengths) / len(all_lengths):.0f}  잘리는 샘플 {over}건  총 토큰 {sum(all_lengths):,}")
    for t, ns in sorted(lengths.items()):
        print(f"   {t:5s} 샘플 {len(ns):4d}개  최대 {max(ns):5d}  평균 {sum(ns) / len(ns):5.0f}")

# 2) 마스크 샘플 -----------------------------------------------------------
print("\n===== 2. 마스크 샘플 ([[ ]] 안이 학습되는 부분) =====")
rows = load_jsonl("data/train.jsonl")
metas = load_jsonl("data/train_meta.jsonl")
s3_dialog = next(r for r, m in zip(rows, metas) if m["type"] == "S3" and len(r["messages"]) >= 5)
others = [next(r for r, m in zip(rows, metas) if m["type"] == t) for t in ["SEED", "S4", "S6"]]
picked = [("S3", ex) for ex in build_examples(tokenizer, s3_dialog["messages"])]  # S3 한 대화 → 샘플 2개
picked += [(t, build_examples(tokenizer, r["messages"])[0]) for t, r in zip(["SEED", "S4", "S6"], others)]

for t, ex in picked:
    prompt = [i for i, y in zip(ex["input_ids"], ex["labels"]) if y == -100]
    answer = [i for i, y in zip(ex["input_ids"], ex["labels"]) if y != -100]
    print(f"\n--- {t} ({ex['turn']}번째 답) ---")
    print(tokenizer.decode(prompt) + "[[" + tokenizer.decode(answer) + "]]")

# 3) 전체 검사: 샘플 수 = assistant 턴 수, 학습 부분이 <|im_end|> 로 끝나고 입력이 생성 시작 표시로 끝나는지 ----
print("\n===== 3. 전체 마스크 검사 =====")
n_samples, bad = 0, 0
for row in rows:
    examples = build_examples(tokenizer, row["messages"])
    n_samples += len(examples)
    if len(examples) != sum(m["role"] == "assistant" for m in row["messages"]):
        bad += 1
    for ex in examples:
        prompt = tokenizer.decode([i for i, y in zip(ex["input_ids"], ex["labels"]) if y == -100])
        answer = tokenizer.decode([i for i, y in zip(ex["input_ids"], ex["labels"]) if y != -100])
        if not answer.endswith("<|im_end|>") or not prompt.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n"):
            bad += 1
print(f"train 대화 {len(rows)}개 → 샘플 {n_samples}개, 이상 {bad}건")
