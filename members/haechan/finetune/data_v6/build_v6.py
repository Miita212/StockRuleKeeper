"""data_v6 = data_v5 + 부등호 라벨 바로잡기(아래 FIXES) + data_aug/aug6 보강 (haechan, 2026-11-08).

1) 부등호 라벨 바로잡기: 문장에 '이상/이하/미만/넘는/초과'가 분명한데 정답 부등호가 어긋난 행.
   (이상→>=, 이하→<=, 미만→<, 넘는·초과→>, '~ 이하/미만인 건 제외'는 남길 범위로 바꾼 부등호)
   사용자 지정 지표가 하나인 추출 행만 본다. 문장 기준으로 직접 읽고 고른 목록이다(전수 점검 결과는 LABEL_AUDIT.md).
2) data_aug/aug6_{train,val}.jsonl 이 있으면 뒤에 붙인다(gen_aug_v6.py 가 만든다).
학습에 쓰지 않는 것: test_haechan/ (시험 전용).
사용: python3 -X utf8 build_v6.py   → train.jsonl / val.jsonl (+ _meta, 커밋하지 않음), EDIT_LOG_v6.csv
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FT = HERE.parent
sys.path.insert(0, str(FT / "data_aug"))
from gen_aug_v6 import amb  # noqa: E402

# (문장, 지표 id, 지금 부등호, 바로잡을 부등호)
FIXES = [
    # 이상 → >=
    ("50천억 이상의 시가총액을 가진 기업", 14, ">", ">="), ("5조 이상의 시가총액을 갖춘 기업들", 14, ">", ">="),
    ("50000억원 이상인 시가총액을 가진 기업", 14, ">", ">="), ("50000억 이상의 시가총액을 가진 기업", 14, ">", ">="),
    ("5조 원 이상인 시가총액을 가진 기업", 14, ">", ">="), ("6개월간 20% 이상 수익 낸 종목", 15, ">", ">="),
    ("반년 동안 20% 이상 수익 낸 종목", 15, ">", ">="), ("20% 이상 수익 낸 6개월 종목", 15, ">", ">="),
    ("6개월 수익률 20% 이상인 종목", 15, ">", ">="), ("1000억 원 이상의 영업이익을 가진 기업", 5, ">", ">="),
    ("배당을 주가의 3% 이상으로 지급하는 기업", 12, ">", ">="), ("이자 전 손익이 3배 이상 이자인 회사", 3, ">", ">="),
    # 넘는 → >
    ("영업이익 증가율이 10%를 넘는 기업", 9, ">=", ">"), ("15% 넘는 매출 성장률을 가진 회사", 8, ">=", ">"),
    # 이하 → <=
    ("시총 1조 이하만 봐야겠어요", 14, "<", "<="), ("시총이 1조 이하인 곳만 보세요", 14, "<", "<="),
    ("1조 이하의 시총 회사만 봐요", 14, "<", "<="), ("1조 이하의 시총 회사들만 주목해", 14, "<", "<="),
    ("시총 1조 이하만 볼래요", 14, "<", "<="), ("PER 10배 이하 주식", 10, "<", "<="),
    # 넘는 제외 / 초과하지 않는 → 남길 범위 <=
    ("100%를 넘는 부채비율은 제외하고 보여줘", 1, "<", "<="), ("100%를 초과하지 않는 부채비율 기업만 보여줘", 1, "<", "<="),
    # 미만 → <
    ("200% 미만을 유지해야 해요", 1, "<=", "<"), ("100% 미만의 부채비율을 가진 회사", 1, "<=", "<"),
    ("부채비율 100% 미만인 회사들만 보여줘", 1, "<=", "<"), ("PBR 1배 미만 주식", 11, "<=", "<"),
    ("PBR 1배 미만", 11, "<=", "<"), ("PER 15배 미만 주식", 10, "<=", "<"), ("20% 미만의 차입금 비중을 가진 기업", 2, "<=", "<"),
    # '0% 이하인 종목은 제외' → 남길 범위는 0% 초과
    ("1년간 수익률이 0% 이하인 종목은 안 봐줘", 15, ">=", ">"), ("1년간 수익률이 0% 이하인 종목은 제외해", 15, ">=", ">"),
    ("최근 1년간 0% 이하 수익률인 종목은 빼줘", 15, ">=", ">"), ("지난 1년간 0% 이하 수익률 종목은 제외해줘", 15, ">=", ">"),
    ("지난 12개월간 손익이 0% 이하인 건 안 봐", 15, ">=", ">"), ("지난 1년간 수익률이 0% 이하인 종목은 제외해줘", 15, ">=", ">"),
]


# 공식 평가셋에서 '규모가 큰 회사'는 시총·거래대금 중 고르는 되묻기(14·19)다. 학습의 '규모' 값 묻기 14(4행)를 같은 기준으로 맞춘다.
RELABEL_AMB = ["규모가 큰 기업들만 골라줘", "작은 규모는 피하고 싶어요", "작은 규모의 회사는 피하고 싶어요", "규모가 작은 회사는 피하고 싶어요"]


def rd(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def main():
    log = []
    out = {}
    for sp in ("train", "val"):
        rows = rd(HERE.parent / "data_v5" / f"{sp}.jsonl")
        meta = rd(HERE.parent / "data_v5" / f"{sp}_meta.jsonl")
        assert len(rows) == len(meta)
        for text, iid, old, new in FIXES:
            hit = 0
            for r, m in zip(rows, meta):
                if len(r["messages"]) != 3 or r["messages"][1]["content"] != text:
                    continue
                d = json.loads(r["messages"][2]["content"])
                for it in d.get("indicators", []):
                    if it["id"] == iid and it["source"] == "user" and it["operator"] == old:
                        it["operator"] = new
                        hit += 1
                        r["messages"][2]["content"] = json.dumps(d, ensure_ascii=False)
                        m["_relabel"] = f"haechan data_v6: 부등호 {old} → {new}"
                        log.append((sp, text, iid, old, new))
            out.setdefault(text, 0)
            out[text] += hit
        for r, m in zip(rows, meta):
            if len(r["messages"]) == 3 and r["messages"][1]["content"] in RELABEL_AMB:
                d = json.loads(r["messages"][2]["content"])
                assert d.get("reason") == "VALUE_MISSING" and d.get("indicator_id") == 14, r["messages"][1]["content"]
                r["messages"][2]["content"] = amb("규모", (14, 19))
                m["_relabel"] = "haechan data_v6: 규모 → 고르기 14·19 (공식 평가셋 기준)"
                log.append((sp, r["messages"][1]["content"], 14, "VALUE_MISSING:14", "AMBIGUOUS_INDICATOR:14,19"))
        aug = HERE.parent / "data_aug" / f"aug6_{sp}.jsonl"
        n_aug = 0
        if aug.exists():
            a_rows, a_meta = rd(aug), rd(HERE.parent / "data_aug" / f"aug6_{sp}_meta.jsonl")
            have = {r["messages"][1]["content"] for r in rows if len(r["messages"]) == 3}
            assert not ({r["messages"][1]["content"] for r in a_rows} & have), "aug6 와 기존 문장이 겹침"
            rows += a_rows
            meta += a_meta
            n_aug = len(a_rows)
        with open(HERE / f"{sp}.jsonl", "w", encoding="utf-8") as f, open(HERE / f"{sp}_meta.jsonl", "w", encoding="utf-8") as g:
            for r, m in zip(rows, meta):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                g.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(f"{sp}: {len(rows)}행 (라벨 바꿈 {sum(1 for l in log if l[0] == sp)}, aug6 {n_aug})")
    missing = [t for t, h in out.items() if h == 0]
    assert not missing, f"못 찾은 행: {missing}"
    with open(HERE / "EDIT_LOG_v6.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["분할", "입력", "지표", "변경 전", "변경 후"])
        w.writerows(log)


if __name__ == "__main__":
    main()
