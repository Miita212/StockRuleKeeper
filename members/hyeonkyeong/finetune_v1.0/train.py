"""Qwen3-8B QLoRA 학습. 기본값 = byungjun/finetune_merged/파인튜닝_설정값_명세.md

사용법:
  python train.py --max_steps 50 --eval_steps 25 --out outputs/smoke   # 스모크 테스트
  python train.py --out outputs/run1                   # 본 학습 (4에폭)
  python train.py --out outputs/run1 --resume          # 끊긴 뒤 마지막 체크포인트에서 이어서
결과: <out>/checkpoint-*/ (0.5에폭마다), <out>/best/ (val loss 최저), <out>/log_history.json
"""
import argparse
import json
import math
import time

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          DataCollatorForSeq2Seq, Trainer, TrainingArguments)

from common import build_examples, load_jsonl

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="models/Qwen3-8B")
parser.add_argument("--out", default="outputs/run1")
parser.add_argument("--epochs", type=float, default=4)
parser.add_argument("--lr", type=float, default=1e-4)
parser.add_argument("--batch_size", type=int, default=4)
parser.add_argument("--grad_accum", type=int, default=4)  # 유효 배치 = 4 x 4 = 16
parser.add_argument("--max_len", type=int, default=2048)
parser.add_argument("--lora_r", type=int, default=32)
parser.add_argument("--lora_alpha", type=int, default=64)
parser.add_argument("--lora_dropout", type=float, default=0.05)
parser.add_argument("--max_steps", type=int, default=-1)
parser.add_argument("--eval_steps", type=int, help="평가·저장 주기 (기본: 0.5에폭). 스모크 테스트에서 평가까지 시험할 때 사용")
parser.add_argument("--resume", action="store_true")
args = parser.parse_args()

# ---------------------------------------------------------------- 데이터
tokenizer = AutoTokenizer.from_pretrained(args.model)


def to_dataset(path):
    examples = []
    for row in load_jsonl(path):
        for ex in build_examples(tokenizer, row["messages"]):  # assistant 턴마다 샘플 1개
            examples.append({"input_ids": ex["input_ids"][:args.max_len], "labels": ex["labels"][:args.max_len]})
    return Dataset.from_list(examples)


train_data = to_dataset("data/train.jsonl")
val_data = to_dataset("data/val.jsonl")

steps_per_epoch = math.ceil(len(train_data) / (args.batch_size * args.grad_accum))
eval_steps = args.eval_steps or math.ceil(steps_per_epoch / 2)  # 기본: 0.5에폭마다 평가·저장
print(f"train {len(train_data)}건, val {len(val_data)}건, 에폭당 {steps_per_epoch}스텝, {eval_steps}스텝마다 평가")

# ---------------------------------------------------------------- 모델 (4비트 + LoRA)
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    quantization_config=BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16,
    ),
    dtype=torch.bfloat16,
    device_map="cuda",
)
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
model = get_peft_model(model, LoraConfig(
    r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout, bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    task_type="CAUSAL_LM",
))
model.print_trainable_parameters()

# ---------------------------------------------------------------- 학습
trainer = Trainer(
    model=model,
    args=TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=0.05,  # 1 미만이면 전체 스텝 대비 비율
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        optim="paged_adamw_8bit",
        weight_decay=0.01,
        max_grad_norm=1.0,
        bf16=True,
        gradient_checkpointing=True,
        train_sampling_strategy="group_by_length",  # 비슷한 길이끼리 묶어 패딩 낭비를 줄임 (packing 은 안 함)
        eval_strategy="steps",
        eval_steps=eval_steps,
        save_strategy="steps",
        save_steps=eval_steps,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        logging_steps=5,
        report_to="none",
        seed=42,
    ),
    train_dataset=train_data,
    eval_dataset=val_data,
    data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100),
)

started = time.time()
trainer.train(resume_from_checkpoint=True if args.resume else None)
elapsed = time.time() - started

# ---------------------------------------------------------------- 저장·요약
trainer.save_model(f"{args.out}/best")
tokenizer.save_pretrained(f"{args.out}/best")
with open(f"{args.out}/log_history.json", "w", encoding="utf-8") as f:
    json.dump(trainer.state.log_history, f, ensure_ascii=False, indent=2)

print("\n===== 요약 =====")
print(f"걸린 시간 {elapsed / 60:.1f}분, 스텝 {trainer.state.global_step}개, 스텝당 {elapsed / max(trainer.state.global_step, 1):.1f}초")
print(f"최대 VRAM {torch.cuda.max_memory_allocated() / 1024 ** 3:.1f}GB")
print(f"best 체크포인트: {trainer.state.best_model_checkpoint}")
print("val loss:")
for log in trainer.state.log_history:
    if "eval_loss" in log:
        print(f"  step {log['step']:4d}  (에폭 {log['epoch']:.1f})  {log['eval_loss']:.4f}")
