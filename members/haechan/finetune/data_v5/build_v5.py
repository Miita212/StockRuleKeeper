"""data_v5 = data_v4 + 되살린 4행 + data_aug 보강 (haechan, 2026-11-06).

- 되살린 4행: data_v4 '추가점검-방향모순'으로 지운 11행 중 피하겠다는 뜻의 문장 4개.
  "고점 대비 -20% 이상 떨어진 주식은 주의/매수 안 좋아/매도 추천/매수 포인트 아냐" → 남길 범위 52주 고점 대비 >= -20 이 맞다
  (평가셋 "30% 넘게 떨어진 주식은 빼줘" 정답 >= -30 과 같은 규칙). 원본 byungjun/finetune_merged 행을 그대로 가져온다.
- 보강: data_aug/aug_train → train, aug_val → val.
- 학습에 쓰지 않는 것: test_haechan/ (시험 전용).
사용: python3 -X utf8 build_v5.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FT = HERE.parent
ORIG = FT.parents[1] / "byungjun" / "finetune_merged"
RESTORE = [
    "최고가 대비 -20% 이상 떨어진 주식은 주의가 필요해요",
    "고점에 비해 -20% 이상 하락한 주식은 매수 안 좋아",
    "신고가 대비 -20% 이상 떨어진 주식은 매도 추천",
    "신고가 대비 -20% 이상 하락한 주식은 매수 포인트 아냐",
]


def rd(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    for sp, aug in (("train", "aug_train"), ("val", "aug_val")):
        rows = rd(FT / "data_v4" / f"{sp}.jsonl")
        meta = rd(FT / "data_v4" / f"{sp}_meta.jsonl")
        assert len(rows) == len(meta)
        have = {r["messages"][1]["content"] for r in rows}
        restored = 0
        if sp == "train":
            o_rows, o_meta = rd(ORIG / "train.jsonl"), rd(ORIG / "train_meta.jsonl")
            for r, m in zip(o_rows, o_meta):
                t = r["messages"][1]["content"]
                if t in RESTORE and t not in have:
                    ans = json.loads(r["messages"][2]["content"])
                    u = [(i["id"], i["operator"], i["value"]) for i in ans["indicators"] if i["source"] == "user"]
                    assert u == [(16, ">=", -20)], (t, u)
                    rows.append(r)
                    meta.append({**m, "_restored": "haechan data_v5: data_v4 추가점검 제거 취소(피하겠다는 뜻이라 정답 맞음)"})
                    have.add(t)
                    restored += 1
            assert restored == len(RESTORE), restored
        a_rows, a_meta = rd(FT / "data_aug" / f"{aug}.jsonl"), rd(FT / "data_aug" / f"{aug}_meta.jsonl")
        assert not ({r["messages"][1]["content"] for r in a_rows} & have)
        rows += a_rows
        meta += a_meta
        with open(HERE / f"{sp}.jsonl", "w", encoding="utf-8") as f, open(HERE / f"{sp}_meta.jsonl", "w", encoding="utf-8") as g:
            for r, m in zip(rows, meta):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                g.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"{sp}: data_v4 {len(rows) - len(a_rows) - restored} + 되살림 {restored} + 보강 {len(a_rows)} = {len(rows)}")


if __name__ == "__main__":
    main()
