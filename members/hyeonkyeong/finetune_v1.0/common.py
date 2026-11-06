"""preflight.py / train.py / evaluate.py 가 같이 쓰는 함수.

턴별 분할: 대화의 assistant 턴마다 학습 샘플을 하나씩 만든다.
  입력  = 그 턴 앞까지의 대화 + 생성 시작 표시 (추론 때와 똑같은 모양, enable_thinking=False → 빈 think 블록 포함)
  정답  = 그 턴의 assistant 답변 + <|im_end|>   ← 이 부분만 loss 에 들어감, 입력은 -100
S3 되묻기(답 2번)는 샘플 2개가 된다. 첫 되묻기도 실제 앱 입력과 같은 모양으로 학습된다.
"""
import json


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def prompt_text(tokenizer, messages):
    """추론용 입력: 주어진 대화 + 생성 시작 표시."""
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )


def build_examples(tokenizer, messages):
    examples = []
    for k, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        prompt_ids = tokenizer(prompt_text(tokenizer, messages[:k]), add_special_tokens=False)["input_ids"]
        answer_ids = tokenizer(message["content"] + "<|im_end|>", add_special_tokens=False)["input_ids"]
        examples.append({
            "input_ids": prompt_ids + answer_ids,
            "labels": [-100] * len(prompt_ids) + answer_ids,
            "turn": sum(m["role"] == "assistant" for m in messages[:k]) + 1,  # 대화 안 몇 번째 답인지
        })
    return examples
