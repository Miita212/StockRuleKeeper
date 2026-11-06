"""병준 병합본(train.jsonl)을 읽어 '직접 추출' 비율을 높인 학습 데이터를 data_v2/ 에 만든다. 원본은 수정하지 않는다.

조정 내용 (평가 결과: 직접 추출 예시가 첫 응답의 5%뿐이라 모델이 '첫 질문엔 되묻기/거절'로 쏠림):
  - SEED 중 첫 응답이 '추출'인 대화(84건)를 --seed-repeat 배로 반복 (기본 4배)
  - S4(수정 요청) 대화를 --s4-keep 비율만 남김 (기본 0.5, 시드 고정 무작위)
  - 나머지(S3·S5·S6·S7·SEED의 되묻기/거절)는 그대로
  - val 은 그대로 복사
평가셋(hyeonkyeong/data/eval_*.jsonl)의 문장이 학습 데이터에 들어 있는지도 검사한다.
"""
import argparse
import glob
import json
import random
import shutil
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEMBERS = HERE.parent.parent
SRC = MEMBERS / "byungjun" / "finetune_merged"
EVAL_GLOB = str(MEMBERS / "hyeonkyeong" / "data" / "eval_*.jsonl")


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def first_kind(msgs):
    try:
        d = json.loads(next(m for m in msgs if m["role"] == "assistant")["content"])
    except Exception:
        return "text"
    if isinstance(d, dict):
        if d.get("needs_clarification"):
            return "clarify"
        if d.get("refusal"):
            return "refuse"
        if "indicators" in d:
            return "extract"
        if "changes" in d:
            return "changes"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-repeat", type=int, default=4)
    ap.add_argument("--s4-keep", type=float, default=0.5)
    ap.add_argument("--out", default=str(HERE / "data_v2"))
    ap.add_argument("--rng", type=int, default=42)
    a = ap.parse_args()

    train = read_jsonl(SRC / "train.jsonl")
    meta = read_jsonl(SRC / "train_meta.jsonl")
    assert len(train) == len(meta), "train 과 train_meta 줄 수가 다름"
    rng = random.Random(a.rng)

    out, before, after = [], Counter(), Counter()
    for rec, m in zip(train, meta):
        t, k = m["type"], first_kind(rec["messages"])
        before[(t, k)] += 1
        if t == "S4":
            if rng.random() >= a.s4_keep:
                continue
            n = 1
        elif t == "SEED" and k == "extract":
            n = a.seed_repeat
        else:
            n = 1
        for _ in range(n):
            out.append(rec)
            after[(t, k)] += 1
    rng.shuffle(out)

    # 평가셋 겹침 검사 (user 문장 기준)
    ev_texts = {r["messages"][1]["content"].strip() for f in glob.glob(EVAL_GLOB) for r in read_jsonl(f)}
    overlap = sorted({m["content"].strip() for rec in out for m in rec["messages"] if m["role"] == "user"} & ev_texts)

    dst = Path(a.out)
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "train.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
    shutil.copy(SRC / "val.jsonl", dst / "val.jsonl")

    print(f"원본 {len(train)}건 → 조정 {len(out)}건  (SEED 추출 x{a.seed_repeat}, S4 {a.s4_keep:.0%} 유지)")
    print("첫 응답 유형 (원본 → 조정):")
    for key in sorted(set(before) | set(after)):
        print(f"  {key[0]:5} {key[1]:8} {before[key]:4} → {after[key]:4}")
    tot = Counter()
    for (t, k), n in after.items():
        tot[k] += n
    print("조정 후 첫 응답 합계:", dict(tot), f"(직접 추출 비율 {100 * tot['extract'] / len(out):.1f}%)")
    print(f"평가셋과 겹치는 user 문장: {len(overlap)}건", overlap[:5])
    print("저장:", dst)


if __name__ == "__main__":
    main()
