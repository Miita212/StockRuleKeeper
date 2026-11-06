"""평가 세트(data/eval.jsonl, 111건)를 모델이 직접 풀게 하고 채점한다.

사용법:
  python evaluate.py --model models/Qwen3-8B                                   # 학습 전 기준선
  python evaluate.py --model models/Qwen3-8B --adapter outputs/run1/checkpoint-316  # 학습 후 (LoRA)
  python evaluate.py --ollama qwen3-8b-stockrule                               # 노트북: GGUF 변환 후
결과: outputs/eval_<이름>/ 에 predictions.jsonl, results.csv, summary.json

채점 항목
  json_valid      : 출력이 JSON 으로 읽히는가
  type_correct    : 답의 종류(지표 / 되묻기 / 거절)가 맞는가
  anchor_exact    : [지표] 사용자가 정한 지표(anchors)의 부등호·값·단위·source 가 모두 맞는가
  all20_exact     : [지표] 20개 전부가 정답과 같은가
  clarify_correct : [되묻기] reason 과 대상 지표(indicator_id 또는 candidates)가 맞는가
  refusal_correct : [거절] 거절했는가
"""
import argparse
import csv
import json
import os
import re
import time

from common import load_jsonl

parser = argparse.ArgumentParser()
parser.add_argument("--model", help="HF 모델 경로 (예: models/Qwen3-8B)")
parser.add_argument("--adapter", help="LoRA 체크포인트 경로")
parser.add_argument("--ollama", help="Ollama 모델 이름")
parser.add_argument("--ollama_url", default="http://localhost:11434")
parser.add_argument("--name", help="결과 폴더 이름 (기본: base / 체크포인트 이름 / ollama)")
parser.add_argument("--batch_size", type=int, default=8)
parser.add_argument("--max_new_tokens", type=int, default=1024)
parser.add_argument("--limit", type=int, help="앞에서 N건만 (스크립트 시험용)")
args = parser.parse_args()


# ---------------------------------------------------------------- 생성
def generate_hf(prompts_messages):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from common import prompt_text

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.bfloat16, device_map="cuda")
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    outputs = []
    for i in range(0, len(prompts_messages), args.batch_size):
        batch = [prompt_text(tokenizer, m) for m in prompts_messages[i:i + args.batch_size]]
        enc = tokenizer(batch, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=args.max_new_tokens, do_sample=False)
        for row in out[:, enc["input_ids"].shape[1]:]:
            outputs.append(tokenizer.decode(row, skip_special_tokens=True))
        print(f"  생성 {len(outputs)}/{len(prompts_messages)}")
    return outputs


def generate_ollama(prompts_messages):
    import requests

    outputs = []
    for messages in prompts_messages:
        res = requests.post(f"{args.ollama_url}/api/chat", json={
            "model": args.ollama, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": 0, "num_predict": args.max_new_tokens},
        })
        outputs.append(res.json()["message"]["content"])
        print(f"  생성 {len(outputs)}/{len(prompts_messages)}")
    return outputs


# ---------------------------------------------------------------- 채점
def parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    start, end = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def answer_type(obj):
    if obj is None:
        return "invalid"
    if obj.get("refusal"):
        return "refusal"
    if obj.get("needs_clarification"):
        return "clarify"
    if "indicators" in obj:
        return "indicators"
    return "other"


def same_indicator(a, b):
    return (a.get("operator") == b.get("operator")
            and float(a.get("value", "nan")) == float(b.get("value", "nan"))
            and a.get("unit") == b.get("unit")
            and a.get("source") == b.get("source"))


def score(gold, pred):
    gold_type, pred_type = answer_type(gold), answer_type(pred)
    result = {"gold_type": gold_type, "pred_type": pred_type,
              "json_valid": pred is not None, "type_correct": gold_type == pred_type}

    if gold_type == "indicators":
        result["anchor_exact"] = result["all20_exact"] = False
        if pred_type == "indicators":
            pred_by_id = {i.get("id"): i for i in pred["indicators"] if isinstance(i, dict)}
            gold_by_id = {i["id"]: i for i in gold["indicators"]}
            try:
                result["anchor_exact"] = all(
                    a in pred_by_id and same_indicator(gold_by_id[a], pred_by_id[a]) for a in gold["anchors"])
                result["all20_exact"] = len(pred_by_id) == 20 and all(
                    i in pred_by_id and same_indicator(g, pred_by_id[i]) for i, g in gold_by_id.items())
            except (TypeError, ValueError):
                pass

    if gold_type == "clarify":
        ok = pred_type == "clarify" and pred.get("reason") == gold["reason"]
        if ok and "indicator_id" in gold:
            ok = pred.get("indicator_id") == gold["indicator_id"]
        if ok and "candidates" in gold:
            gold_ids = {c["id"] for c in gold["candidates"]}
            pred_ids = {c.get("id") for c in pred.get("candidates", []) if isinstance(c, dict)}
            ok = gold_ids == pred_ids
        result["clarify_correct"] = ok

    if gold_type == "refusal":
        result["refusal_correct"] = pred_type == "refusal"

    return result


def rate(rows, key):
    values = [r[key] for r in rows if key in r]
    return (sum(values) / len(values), len(values)) if values else (None, 0)


# ---------------------------------------------------------------- 실행
rows = load_jsonl("data/eval.jsonl")[:args.limit]
prompts = [r["messages"][:-1] for r in rows]  # system + user

if args.ollama:
    name = args.name or f"ollama_{args.ollama.replace(':', '_')}"
    generate = generate_ollama
else:
    name = args.name or (os.path.basename(args.adapter.rstrip("/")) if args.adapter else "base")
    generate = generate_hf

out_dir = f"outputs/eval_{name}"
os.makedirs(out_dir, exist_ok=True)

print(f"평가 {len(rows)}건 → {out_dir}")
started = time.time()
outputs = generate(prompts)
elapsed = time.time() - started

results = []
for row, text in zip(rows, outputs):
    pred = parse_json(text)
    results.append({"eval_id": row["eval_id"], "kind": row["kind"], "text": row["text"],
                    **score(row["output"], pred), "output": text})

with open(f"{out_dir}/predictions.jsonl", "w", encoding="utf-8") as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

columns = ["eval_id", "kind", "text", "gold_type", "pred_type", "json_valid", "type_correct",
           "anchor_exact", "all20_exact", "clarify_correct", "refusal_correct"]
with open(f"{out_dir}/results.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)

summary = {"name": name, "n": len(results), "seconds": round(elapsed, 1),
           "seconds_per_item": round(elapsed / len(results), 2)}
print(f"\n===== 결과: {name} ({len(results)}건, 1건당 {summary['seconds_per_item']}초) =====")
for key in ["json_valid", "type_correct", "anchor_exact", "all20_exact", "clarify_correct", "refusal_correct"]:
    value, n = rate(results, key)
    summary[key] = value
    print(f"  {key:16s} {'-' if value is None else f'{value * 100:5.1f}%'}  (n={n})")

with open(f"{out_dir}/summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
