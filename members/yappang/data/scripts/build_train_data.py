"""학습용 데이터 생성: 병합 결과에 수정 규칙(data_fixes.py)을 적용해 data/train_data/ 에 쓴다. 8B(팀)·Q4B 학습 모두 이 결과를 쓴다.

흐름
  1. 병합 결과 train/val(+메타)을 얻는다.
       - 팀원 폴더(haechan·hyeonkyeong·byungjun)의 원본 파일이 다 있으면 train_model_q4b/scripts/merge_train_sets.py 로 새로 병합한다.
       - 없으면(이 PC처럼 members/ 에 yappang 만 있을 때) 병합 완료본(기본 train_model_q4b/data/backup)을 쓴다. --from-merged 로 고른다.
  2. 수정 규칙을 적용한다(부등호 경계·조사 수정, 반전·깨진 문장 제외). 분할(train/val)은 병합 때 정해진 대로 유지한다.
  3. 결과를 검사하고, 파일명에 _fixed 를 붙여 쓴다. 건별 내역은 fix_log.csv, 요약은 build_report.json.

실행 (members/yappang 에서)
  python -I -X utf8 data/scripts/build_train_data.py
  python -I -X utf8 data/scripts/build_train_data.py --from-merged train_model_q4b/data/backup --out data/train_data
출력(기본 data/train_data/): train_fixed.jsonl, val_fixed.jsonl, train_meta_fixed.jsonl, val_meta_fixed.jsonl, fix_log.csv, build_report.json
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAPPANG = HERE.parents[1]          # .../members/yappang
MEMBERS = YAPPANG.parent           # .../members
sys.path.insert(0, str(HERE))
import data_fixes  # noqa: E402

MERGE_SCRIPT = YAPPANG / "train_model_q4b" / "scripts" / "merge_train_sets.py"
Q4B_DATA = YAPPANG / "train_model_q4b" / "data"
NAMES = ["train", "val"]


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sources_present():
    """merge_train_sets.py 가 읽는 팀원 원본 파일이 모두 있는지."""
    sys.path.insert(0, str(MERGE_SCRIPT.parent))
    import merge_train_sets as m
    files = [rel for _, rel in m.TRAIN_FILES] + list(m.EVAL_FILES) + [item[1] for item in m.EXTRA_FILES]
    missing = [rel for rel in files if not (MEMBERS / rel).exists()]
    return missing


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-merged", default=None, help="병합 완료된 train/val/meta 폴더. 없으면 가능할 때 새로 병합한다")
    ap.add_argument("--out", default=str(YAPPANG / "data" / "train_data"))
    a = ap.parse_args()

    tmp = None
    if a.from_merged:
        merged = Path(a.from_merged).resolve()
        how = f"병합 완료본 {merged}"
    else:
        missing = sources_present()
        if missing:
            merged = (Q4B_DATA / "backup").resolve()
            how = f"병합 완료본 {merged} (팀원 원본 {len(missing)}개 없음: {missing[0]} 등)"
            print("※ 팀원 폴더의 원본 파일이 없어 새로 병합할 수 없다. 병합 완료본을 사용한다.")
        else:
            tmp = tempfile.TemporaryDirectory()
            subprocess.run([sys.executable, "-I", "-X", "utf8", str(MERGE_SCRIPT), "--no-fix", "--out", tmp.name], check=True)
            merged = Path(tmp.name)
            how = "merge_train_sets.py 로 새로 병합"
    print("입력:", how)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"입력": how, "병합 파일 sha256": {}, "결과": {}}
    all_log = []
    result = {}
    for nm in NAMES:
        rows, metas = read_jsonl(merged / f"{nm}.jsonl"), read_jsonl(merged / f"{nm}_meta.jsonl")
        if len(rows) != len(metas):
            sys.exit(f"[중단] {nm}: 대화 {len(rows)}개, 메타 {len(metas)}개로 줄 수가 다르다")
        for suf in ("", "_meta"):
            report["병합 파일 sha256"][f"{nm}{suf}.jsonl"] = sha(merged / f"{nm}{suf}.jsonl")
        nr, nm_, log = data_fixes.apply(rows, metas)
        for l in log:
            all_log.append((nm,) + l)
        result[nm] = (nr, nm_)
        print(f"{nm:5} {len(rows)} → {len(nr)}  (수정 {sum(1 for l in log if l[2] == '수정')}, 제외 {sum(1 for l in log if l[2] == '제외')})")

    # 결과 검사
    problems = []
    tr, va = result["train"][0], result["val"][0]
    tf = {data_fixes.first_user(r) for r in tr}
    vf = {data_fixes.first_user(r) for r in va}
    if tf & vf:
        problems.append(f"train/val 첫 질문 겹침 {len(tf & vf)}건")
    evp = Q4B_DATA / "eval_set.jsonl"
    if evp.exists():
        ev = {json.loads(l)["text"].strip() for l in evp.read_text(encoding="utf-8").splitlines() if l.strip()}
        if (tf | vf) & ev:
            problems.append(f"평가 문장이 학습에 섞임 {len((tf | vf) & ev)}건")
    for r in tr + va:
        roles = [m["role"] for m in r["messages"]]
        if not (roles[0] == "system" and roles[-1] == "assistant" and len(roles) >= 3
                and all(x == ("user" if i % 2 == 0 else "assistant") for i, x in enumerate(roles[1:]))):
            problems.append("메시지 순서 이상")
            break
    for nm in NAMES:
        for r in result[nm][0]:
            last = r["messages"][-1]["content"]
            if last.startswith("{"):
                try:
                    json.loads(last)
                except ValueError:
                    problems.append(f"{nm}: 정답 JSON 파싱 실패")
                    break

    # 쓰기
    for nm in NAMES:
        rows, metas = result[nm]
        for fname, data in ((f"{nm}_fixed.jsonl", rows), (f"{nm}_meta_fixed.jsonl", metas)):
            with open(out / fname, "w", encoding="utf-8", newline="\n") as f:
                for x in data:
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
            report["결과"][fname] = {"lines": len(data), "sha256": sha(out / fname)}
    with open(out / "fix_log.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["대상", "행번호(1부터)", "유형", "조치", "입력(앞 60자)", "내용"])
        w.writerows(all_log)
    report["조치 건수"] = dict(Counter(f"{l[0]}:{l[3]}" for l in all_log))
    report["검사 문제"] = problems

    # 현재 Q4B 학습 데이터(train_model_q4b/data/*_fixed)와 같은지
    same = []
    for fname in report["결과"]:
        q = Q4B_DATA / fname
        if q.exists():
            same.append((fname, sha(q) == report["결과"][fname]["sha256"]))
    report["Q4B 학습 데이터와 동일 여부"] = {k: ("동일" if v else "다름") for k, v in same}
    (out / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[검사]", "통과" if not problems else "문제 있음")
    for p in problems:
        print("  -", p)
    for k, v in same:
        print(f"  Q4B 학습 데이터 {k}: {'동일' if v else '다름'}")
    print("출력:", out)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
