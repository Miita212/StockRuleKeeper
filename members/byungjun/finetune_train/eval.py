"""학습한 어댑터 평가 (byungjun 개인 관리본).

eval_*.jsonl 의 각 문항에 대해 모델이 생성한 답을 정답(output)과 비교한다.
  - JSON 유효율 : 답이 JSON 으로 파싱되는 비율
  - 형태 일치율 : 정답과 최상위 키가 같은 비율 (indicators / needs_clarification / 거절 등 구분)
  - 완전 일치율 : 파싱한 JSON 이 정답과 완전히 같은 비율
  - kind 별 완전 일치율

사용 (서버에서):
    python eval.py --adapter runs/v1 --eval data/eval_1-7.jsonl data/eval_8-13.jsonl data/eval_14-20.jsonl
    python eval.py --eval data/eval_*.jsonl      # 어댑터 없이 → 학습 전 기준선
"""
import argparse
import collections
import json

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen3-8B")
ap.add_argument("--adapter", default=None)
ap.add_argument("--eval", nargs="+", required=True)
ap.add_argument("--out", default="eval_result.jsonl")
ap.add_argument("--batch", type=int, default=8)
args = ap.parse_args()

tok = AutoTokenizer.from_pretrained(args.model, padding_side="left")
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                           bnb_4bit_use_double_quant=True,
                                           bnb_4bit_compute_dtype=torch.bfloat16),
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
)
if args.adapter:
    model = PeftModel.from_pretrained(model, args.adapter)
model.eval()

rows = [json.loads(line) for path in args.eval for line in open(path, encoding="utf-8") if line.strip()]

results = []
for start in range(0, len(rows), args.batch):
    chunk = rows[start:start + args.batch]
    prompts = [tok.apply_chat_template(r["messages"][:2], tokenize=False,
                                       add_generation_prompt=True, enable_thinking=False) for r in chunk]
    inputs = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=1200, do_sample=False)
    for r, g in zip(chunk, generated):
        text = tok.decode(g[inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        results.append({"eval_id": r["eval_id"], "kind": r["kind"], "text": r["text"],
                        "expected": r["output"], "generated": text, "parsed": parsed})
    print(f"{len(results)}/{len(rows)}", flush=True)

with open(args.out, "w", encoding="utf-8") as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

valid = shape = exact = 0
by_kind = collections.defaultdict(lambda: [0, 0])
for r in results:
    ok = r["parsed"] is not None and r["parsed"] == r["expected"]
    valid += r["parsed"] is not None
    shape += isinstance(r["parsed"], dict) and set(r["parsed"]) == set(r["expected"])
    exact += ok
    by_kind[r["kind"]][0] += ok
    by_kind[r["kind"]][1] += 1

n = len(results)
print(f"\nJSON 유효율 {valid}/{n} = {valid / n:.1%}")
print(f"형태 일치율 {shape}/{n} = {shape / n:.1%}")
print(f"완전 일치율 {exact}/{n} = {exact / n:.1%}")
for kind, (ok, total) in sorted(by_kind.items()):
    print(f"  {kind}: {ok}/{total}")
print(f"자세한 결과: {args.out}")
