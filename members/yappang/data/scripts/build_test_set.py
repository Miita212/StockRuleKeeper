"""통합 시험 세트 test_set.jsonl 생성 (2026-11-09, yappang).  8B·4B 공용, 학습·검증에 쓰지 않는다.

합치는 것: 공식 111문항(members/hyeonkyeong/data/eval_*.jsonl = 백업된 train_model_q4b/data/backup/2026-11-09/eval_set.jsonl 과 같은 문장)
         + haechan 시험 123문항(members/haechan/finetune/test_haechan/test_haechan.jsonl 58, test_haechan_v5.jsonl 31, test_haechan_v7.jsonl 34)
각 행: test_id(T001~), source(official111 | haechan58 | haechan31 | haechan34), orig_id(원래 id), eval_id(=orig_id, 평가 스크립트 호환), id(=orig_id, haechan 평가 호환),
       kind, text, output, messages  (원본 필드는 고치지 않았다. 단 거절 정답 문구의 조사 오류만 fix_refusal_josa 로 고친다: 2026-11-09 팀 합의)
결과: train_model_q4b/data/test_set.jsonl
사용 (members/yappang 에서):
  python3 -I -X utf8 data/scripts/build_test_set.py --haechan <test_haechan 폴더> [--train-val train_fixed4.jsonl val_fixed4.jsonl]
검사: 문장 중복, id 중복, 학습·검증 파일과 문장 동일 여부(있으면 실패).
"""
import argparse, collections, hashlib, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # members/yappang
SRC = [("official111", ROOT / "train_model_q4b" / "data" / "backup" / "2026-11-09" / "eval_set.jsonl", "eval_id"),
       ("haechan58", "test_haechan.jsonl", "id"), ("haechan31", "test_haechan_v5.jsonl", "id"), ("haechan34", "test_haechan_v7.jsonl", "id")]


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


import re


def _final(ch):  # 받침 번호(0=없음, 8=ㄹ)
    return (ord(ch[-1]) - 0xAC00) % 28 if "가" <= ch[-1] <= "힣" else 0


def fix_refusal_josa(out):
    """'X는 아직 쓰지 … A나 B 볼 수 있어요' → 'X은/는 …, A이나/나 B으로/로 볼 수 있어요'. 이미 맞은 문장은 그대로."""
    if not (isinstance(out, dict) and out.get("refusal")):
        return out
    m = re.fullmatch(r"(.+?)(는|은) 아직 쓰지 않는 지표예요\. (.+?)(?:이나|나) (.+?)(?:으로|로)? 볼 수 있어요\.", out["message"])
    if not m or out["message"].endswith("로 볼 수 있어요."):
        return out
    x, _, a_, b = m.groups()
    msg = "%s%s 아직 쓰지 않는 지표예요. %s%s %s%s 볼 수 있어요." % (
        x, "은" if _final(x) else "는", a_, "이나" if _final(a_) else "나", b, "로" if _final(b) in (0, 8) else "으로")
    return {**out, "message": msg}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--haechan", required=True, help="haechan test_haechan 폴더 (jsonl 3개가 있는 곳)")
    ap.add_argument("--data", default=str(ROOT / "train_model_q4b" / "data"))
    ap.add_argument("--train-val", nargs="+", default=["train_fixed4.jsonl", "val_fixed4.jsonl"])
    a = ap.parse_args()
    rows = []
    for src, path, key in SRC:
        p = Path(path) if isinstance(path, Path) else Path(a.haechan) / path
        for r in load(p):
            o = {"test_id": "T%03d" % (len(rows) + 1), "source": src, "orig_id": r[key], "eval_id": r[key], "id": r[key],
                 "kind": r["kind"], "text": r["text"], "output": fix_refusal_josa(r["output"]), "messages": r["messages"]}
            rows.append(o)
    texts = [r["text"].strip() for r in rows]
    assert len(set(texts)) == len(texts), "문장 중복"
    assert len({r["orig_id"] for r in rows}) == len(rows), "id 중복"
    for n in a.train_val:
        s = {json.loads(l)["messages"][1]["content"].strip() for l in open(Path(a.data) / n, encoding="utf-8")}
        both = set(texts) & s
        assert not both, "%s 와 겹침: %s" % (n, sorted(both)[:5])
    out = Path(a.data) / "test_set.jsonl"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = collections.Counter(r["source"] for r in rows)
    print(len(rows), dict(c), "sha256", hashlib.sha256(out.read_bytes()).hexdigest())


main()
