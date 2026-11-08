"""data_v7 = data_v6 + data_aug/aug7 보강 (haechan, 2026-11-08).
aug7 은 gen_aug_v7.py 가 만든다(20개 밖 개념 거절·지표 번호 혼동·부등호 표현·되묻기 말투).
기존 데이터의 라벨은 바꾸지 않는다. 덩치/몸집(값 묻기)과 규모(고르기)의 기준 차이는 팀 기준이 정해질 때까지 그대로 둔다.
학습에 쓰지 않는 것: test_haechan/ (시험 전용).
사용: python3 -X utf8 build_v7.py   → train.jsonl / val.jsonl (+ _meta, 커밋하지 않음)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FT = HERE.parent


def rd(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    for sp in ("train", "val"):
        rows, meta = rd(FT / "data_v6" / f"{sp}.jsonl"), rd(FT / "data_v6" / f"{sp}_meta.jsonl")
        assert len(rows) == len(meta)
        a_rows, a_meta = rd(FT / "data_aug" / f"aug7_{sp}.jsonl"), rd(FT / "data_aug" / f"aug7_{sp}_meta.jsonl")
        have = {r["messages"][1]["content"] for sp2 in ("train", "val") for r in rd(FT / "data_v6" / f"{sp2}.jsonl") if len(r["messages"]) == 3}
        assert not ({r["messages"][1]["content"] for r in a_rows} & have), "aug7 과 기존 문장이 겹침"
        for r in a_rows:
            assert [m["role"] for m in r["messages"]] == ["system", "user", "assistant"]
            json.loads(r["messages"][2]["content"])
        rows += a_rows
        meta += a_meta
        with open(HERE / f"{sp}.jsonl", "w", encoding="utf-8") as f, open(HERE / f"{sp}_meta.jsonl", "w", encoding="utf-8") as g:
            for r, m in zip(rows, meta):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                g.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"{sp}: {len(rows)}행 (aug7 {len(a_rows)})")


if __name__ == "__main__":
    main()
