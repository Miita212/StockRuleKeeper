"""Qwen3-8B QLoRA 학습 (byungjun 개인 관리본).

데이터: finetune_merged/train.jsonl, val.jsonl  (한 줄 = {"messages": [...]})
방식: assistant 답변마다 샘플 1개. 앞 대화(질문)는 loss 제외, 답변 + <|im_end|>만 학습.

사용:
    python train.py --dry-run                 # 토큰 길이만 확인 (GPU 불필요)
    python train.py --max-steps 50            # 스모크 테스트
    python train.py --out runs/v1             # 본 학습
"""
import argparse
import json
import statistics

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          Trainer, TrainingArguments, set_seed)

IGNORE = -100

ap = argparse.ArgumentParser()
ap.add_argument("--model", default="Qwen/Qwen3-8B")
ap.add_argument("--train", default="data/train.jsonl")
ap.add_argument("--val", default="data/val.jsonl")
ap.add_argument("--out", default="runs/v1")
ap.add_argument("--max-len", type=int, default=2048)
ap.add_argument("--epochs", type=float, default=3)
ap.add_argument("--lr", type=float, default=1e-4)
ap.add_argument("--batch", type=int, default=4)
ap.add_argument("--accum", type=int, default=4)
ap.add_argument("--max-steps", type=int, default=-1)
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

tok = AutoTokenizer.from_pretrained(args.model)


def load(path):
    samples = []
    for line in open(path, encoding="utf-8"):
        messages = json.loads(line)["messages"]
        for i, m in enumerate(messages):
            if m["role"] != "assistant":
                continue
            prompt = tok.apply_chat_template(messages[:i], tokenize=False,
                                             add_generation_prompt=True, enable_thinking=False)
            prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
            answer_ids = tok(m["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
            if len(prompt_ids) + len(answer_ids) > args.max_len:
                continue
            samples.append({"input_ids": prompt_ids + answer_ids,
                            "labels": [IGNORE] * len(prompt_ids) + answer_ids})
    return samples


train, val = load(args.train), load(args.val)
lengths = [len(s["input_ids"]) for s in train]
print(f"train {len(train)}개, val {len(val)}개, 길이 평균 {statistics.mean(lengths):.0f} / 최대 {max(lengths)}")
if args.dry_run:
    raise SystemExit

set_seed(42)
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                           bnb_4bit_use_double_quant=True,
                                           bnb_4bit_compute_dtype=torch.bfloat16),
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
)
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model = get_peft_model(model, LoraConfig(
    r=32, lora_alpha=64, lora_dropout=0.05, task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
model.print_trainable_parameters()


def collate(batch):
    n = max(len(b["input_ids"]) for b in batch)
    pad = tok.pad_token_id
    return {
        "input_ids": torch.tensor([b["input_ids"] + [pad] * (n - len(b["input_ids"])) for b in batch]),
        "labels": torch.tensor([b["labels"] + [IGNORE] * (n - len(b["labels"])) for b in batch]),
        "attention_mask": torch.tensor([[1] * len(b["input_ids"]) + [0] * (n - len(b["input_ids"])) for b in batch]),
    }


steps_per_epoch = len(train) // (args.batch * args.accum)
total_steps = args.max_steps if args.max_steps > 0 else int(steps_per_epoch * args.epochs)
trainer = Trainer(
    model=model,
    train_dataset=train,
    eval_dataset=val,
    data_collator=collate,
    args=TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=int(total_steps * 0.05),
        optim="paged_adamw_8bit",
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=steps_per_epoch // 2,
        save_strategy="steps",
        save_steps=steps_per_epoch // 2,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        remove_unused_columns=False,
    ),
)
trainer.train()
trainer.save_model(args.out)
tok.save_pretrained(args.out)
