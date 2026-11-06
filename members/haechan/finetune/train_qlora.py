"""Qwen3-8B QLoRA 파인튜닝 (4090 한 장).

데이터: members/byungjun/finetune_merged/train.jsonl, val.jsonl  (한 줄 = {"messages": [system, user, assistant, ...]})

loss 범위: assistant 답변 전부. 대화가 여러 턴(S3 되묻기)이면 assistant 턴마다 학습 샘플을 하나씩 만든다.
  - 샘플 = (그 턴 앞까지의 대화 + 생성 시작 표시)  →  정답 = 그 턴의 assistant 답변 + <|im_end|>
  - 생성 시작 표시는 추론 때와 같게 enable_thinking=False 로 만든다(빈 <think> 블록 포함).
  - 템플릿 문법을 건드리지 않아서 transformers 버전이 바뀌어도 마스크가 어긋나지 않는다.

사용:
    python -X utf8 train_qlora.py --dry-run                 # GPU 없이 토큰 길이·샘플 1개만 확인
    python -X utf8 train_qlora.py --out runs/qwen3-8b-v1    # 학습
"""
import argparse
import json
import random
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parent.parent / "byungjun" / "finetune_merged"
IGNORE = -100


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def check_messages(msgs, where):
    """system 뒤에 user/assistant 가 번갈아 나오고 마지막이 assistant 인지 확인."""
    roles = [m["role"] for m in msgs]
    ok = roles[0] == "system" and roles[-1] == "assistant" and len(roles) >= 3
    ok = ok and all(r == ("user" if i % 2 == 0 else "assistant") for i, r in enumerate(roles[1:]))
    if not ok:
        raise ValueError(f"{where}: 역할 순서가 이상함 {roles}")


def build_examples(records, tokenizer, max_len, where):
    """대화 → (input_ids, labels) 목록. max_len 을 넘으면 자르지 않고 버린다(JSON 이 잘리면 안 되므로)."""
    examples, dropped = [], 0
    for n, rec in enumerate(records, 1):
        msgs = rec["messages"]
        check_messages(msgs, f"{where} {n}번째 줄")
        for k, m in enumerate(msgs):
            if m["role"] != "assistant":
                continue
            prompt = tokenizer.apply_chat_template(
                msgs[:k], tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            target = m["content"] + "<|im_end|>\n"
            p_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            t_ids = tokenizer(target, add_special_tokens=False)["input_ids"]
            ids = p_ids + t_ids
            if len(ids) > max_len:
                dropped += 1
                continue
            # 마지막 "\n" 은 loss 에서 뺀다(<|im_end|> 까지만 학습)
            labels = [IGNORE] * len(p_ids) + t_ids[:-1] + [IGNORE]
            examples.append({"input_ids": ids, "labels": labels, "turn": sum(1 for x in msgs[:k] if x["role"] == "assistant")})
    return examples, dropped


def describe(name, examples, dropped):
    lens = [len(e["input_ids"]) for e in examples]
    tgt = [sum(1 for x in e["labels"] if x != IGNORE) for e in examples]
    print(f"[{name}] 샘플 {len(examples)}개 (너무 길어 버린 것 {dropped}개)")
    if lens:
        print(f"  전체 길이 평균 {statistics.mean(lens):.0f} / 최대 {max(lens)} 토큰, 정답 길이 평균 {statistics.mean(tgt):.0f} / 최대 {max(tgt)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-8B")
    ap.add_argument("--train", default=str(DEFAULT_DATA / "train.jsonl"))
    ap.add_argument("--val", default=str(DEFAULT_DATA / "val.jsonl"))
    ap.add_argument("--out", default=str(HERE / "runs" / "qwen3-8b-v1"))
    ap.add_argument("--max-len", type=int, default=2048)
    ap.add_argument("--epochs", type=float, default=3)
    ap.add_argument("--lr", type=float, default=1e-4, help="byungjun 명세 1e-4 (불안정하면 5e-5, 느리면 2e-4)")
    ap.add_argument("--max-steps", type=int, default=-1, help="스모크 테스트용. 예: 50 (-1 이면 에폭 기준)")
    ap.add_argument("--eval-steps", type=int, default=0, help="평가·저장 간격(스텝). 0 이면 0.5 에폭마다")
    ap.add_argument("--keep-ckpts", type=int, default=3, help="체크포인트를 최근 몇 개 남길지 (최저 val loss 체크포인트는 따로 남음)")
    ap.add_argument("--early-stop", type=int, default=0, help="val loss 가 N번 연속(평가 간격 기준) 나아지지 않으면 멈춤. 0 이면 끔. 최저 체크포인트는 load_best_model_at_end 로 남는다")
    ap.add_argument("--resume", default=None, help="체크포인트 폴더에서 이어서 학습 (학습률 일정·옵티마이저 상태 포함). 다른 설정은 처음과 같게")
    ap.add_argument("--group-by-length", action="store_true",
                    help="길이가 비슷한 샘플끼리 배치. 기본 끔: 답 유형마다 길이가 달라 배치가 한 유형으로 몰리고 v1·v2가 한 유형으로 쏠렸다")
    ap.add_argument("--batch", type=int, default=2, help="GPU 한 번에 처리하는 샘플 수 (16GB 기준. 24GB 면 4)")
    ap.add_argument("--accum", type=int, default=8, help="gradient accumulation (실효 배치 = batch x accum = 16)")
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--alpha", type=int, default=64)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true", help="GPU·torch 없이 토큰화만 확인")
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.model)
    train_recs, val_recs = read_jsonl(args.train), read_jsonl(args.val)
    train_ex, d1 = build_examples(train_recs, tok, args.max_len, "train")
    val_ex, d2 = build_examples(val_recs, tok, args.max_len, "val")
    print(f"원본 대화: train {len(train_recs)} / val {len(val_recs)}")
    describe("train", train_ex, d1)
    describe("val", val_ex, d2)

    # 샘플 하나를 눈으로 확인: 회색(마스크) 부분은 loss 에 안 들어간다
    rng = random.Random(args.seed)
    picks = rng.sample(train_ex, 3) + rng.sample([x for x in train_ex if x["turn"] > 0], 2)  # 3개 + 다중 턴(2번째 이후 답변) 2개
    for i, e in enumerate(picks, 1):
        learn = [t for t, y in zip(e["input_ids"], e["labels"]) if y != IGNORE]
        print(f"\n--- 샘플 {i} (대화 안 {e['turn'] + 1}번째 답변): 학습 대상 ---")
        print(tok.decode(learn))
        print("    [마스크된 앞부분 끝 60자]", repr(tok.decode([t for t, y in zip(e["input_ids"], e["labels"]) if y == IGNORE])[-60:]))
    ends = sum(1 for e in train_ex if tok.decode([t for t, y in zip(e["input_ids"], e["labels"]) if y != IGNORE]).endswith("<|im_end|>"))
    print(f"\n정답이 <|im_end|> 로 끝나는 샘플: {ends}/{len(train_ex)}  (전부여야 정상)")
    if args.dry_run:
        return

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import BitsAndBytesConfig, EarlyStoppingCallback, Trainer, TrainingArguments, set_seed

    set_seed(args.seed)
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        args.model, quantization_config=bnb, torch_dtype=torch.bfloat16, device_map={"": 0}
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.rank,
            lora_alpha=args.alpha,
            lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id

    def collate(batch):
        n = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
        lab = torch.full((len(batch), n), IGNORE, dtype=torch.long)
        att = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):
            L = len(b["input_ids"])
            ids[i, :L] = torch.tensor(b["input_ids"])
            lab[i, :L] = torch.tensor(b["labels"])
            att[i, :L] = 1
        return {"input_ids": ids, "labels": lab, "attention_mask": att}

    # 0.5 에폭마다 평가·저장 (byungjun 명세). 샘플을 턴 단위로 풀어서 에폭당 스텝은 명세(131)보다 많다.
    steps_per_epoch = max(1, -(-len(train_ex) // (args.batch * args.accum)))
    half_epoch = args.eval_steps or max(1, steps_per_epoch // 2)
    total_steps = args.max_steps if args.max_steps > 0 else int(steps_per_epoch * args.epochs)
    print(f"에폭당 약 {steps_per_epoch}스텝, 평가·저장 {half_epoch}스텝마다, 전체 약 {total_steps}스텝, group_by_length={args.group_by_length}")
    targs = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        # byungjun train.py(정상 학습 확인됨)와 맞춤: warmup 은 스텝 수로, weight_decay 는 기본값(0)
        warmup_steps=int(total_steps * 0.05),
        max_grad_norm=1.0,
        optim="paged_adamw_8bit",
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=half_epoch,
        save_strategy="steps",
        save_steps=half_epoch,
        save_total_limit=args.keep_ckpts,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        group_by_length=args.group_by_length,
        report_to="none",
        seed=args.seed,
        remove_unused_columns=False,
    )
    callbacks = [EarlyStoppingCallback(early_stopping_patience=args.early_stop)] if args.early_stop > 0 else []
    trainer = Trainer(model=model, args=targs, train_dataset=train_ex, eval_dataset=val_ex, data_collator=collate, callbacks=callbacks)
    trainer.train(resume_from_checkpoint=args.resume)
    trainer.save_model(args.out)  # LoRA 어댑터만 저장(합치기·양자화는 따로)
    tok.save_pretrained(args.out)
    print("저장 완료:", args.out)


if __name__ == "__main__":
    main()
