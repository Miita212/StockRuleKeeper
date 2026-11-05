"""반도체 종목 풀(고정 종목 리스트)을 만들어 stocks 표에 넣는다.

1) 한투 종목 마스터 파일(공개)로 코스피·코스닥 전 종목 코드를 얻고
2) 종목기본정보로 산업분류·지수 업종을 받아 반도체 종목을 자동 선별(source=auto)하고
   data/semiconductor_exclude.json 의 비반도체 종목을 뺀 뒤
3) data/semiconductor_manual.json 의 대표 종목을 수동 보강(source=manual)한다.
결과: data/semiconductor_universe.json + stocks 표.

사용 (backend 폴더에서):
  python batch/build_universe.py              # 수집(이어받기) + 저장, 약 30분
  python batch/build_universe.py --from-cache # 수집 없이 .cache 진행 파일로 목록만 다시 만든다
"""
import argparse
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from db.database import connect, init_db  # noqa: E402
from external.kis import quotes  # noqa: E402

OUT = config.ROOT / "data" / "semiconductor_universe.json"
MANUAL = config.ROOT / "data" / "semiconductor_manual.json"
EXCLUDE = config.ROOT / "data" / "semiconductor_exclude.json"
PROGRESS = config.ROOT / ".cache" / "universe_progress.json"
MASTERS = {  # 시장: (URL, 행 끝 고정폭 길이)
    "KOSPI": ("https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip", 227),
    "KOSDAQ": ("https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip", 221),
}
KEYWORD = "반도체"


def load_master(market: str) -> list[dict]:
    url, tail_len = MASTERS[market]
    with urllib.request.urlopen(url, timeout=60) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    rows = []
    for line in z.read(z.namelist()[0]).splitlines():
        head, tail = line[:-tail_len], line[-tail_len:]
        code = head[0:9].decode("cp949", "replace").strip()
        name = head[21:].decode("cp949", "replace").strip()
        if tail[0:2] == b"ST" and len(code) == 6:  # 주식만(ETF·ETN·리츠 제외)
            rows.append({"code": code, "name": name, "market": market})
    return rows


def classify(code: str) -> dict:
    p = quotes.get_profile(code)
    return {"std_idst_clsf_cd_name": p["industry_name"], "idx_bztp_mcls_cd_name": p["sector_names"][0],
            "idx_bztp_scls_cd_name": p["sector_names"][1]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-cache", action="store_true")
    args = ap.parse_args()

    stocks = [s for m in MASTERS for s in load_master(m)]
    print(f"주식 종목 수: {len(stocks)}")
    PROGRESS.parent.mkdir(exist_ok=True)
    done = json.loads(PROGRESS.read_text(encoding="utf-8")) if PROGRESS.exists() else {}
    if not args.from_cache:
        for i, s in enumerate(stocks, 1):
            if s["code"] in done and "error" not in done[s["code"]]:
                continue
            try:
                done[s["code"]] = classify(s["code"])
            except Exception as e:  # 실패한 종목은 기록하고 계속 간다
                done[s["code"]] = {"error": str(e)}
            if i % 50 == 0:
                PROGRESS.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
                print(f"{i}/{len(stocks)}")
        PROGRESS.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")

    # 자동 선별: 산업분류가 "반도체 제조업"이거나, 거래소 지수 업종(소분류)이 "반도체"인 종목.
    # 산업분류가 반도체로 잡히지 않는 장비·소재·후공정 종목은 지수 업종으로 보완한다.
    def is_semi(c: str) -> bool:
        v = done.get(c, {})
        return KEYWORD in str(v.get("std_idst_clsf_cd_name")) or v.get("idx_bztp_scls_cd_name") == KEYWORD

    excluded = {e["code"] for e in json.loads(EXCLUDE.read_text(encoding="utf-8"))} if EXCLUDE.exists() else set()
    auto = [{**s, "industry_name": done[s["code"]].get("std_idst_clsf_cd_name"), "source": "auto"}
            for s in stocks if is_semi(s["code"]) and s["code"] not in excluded]
    manual = json.loads(MANUAL.read_text(encoding="utf-8")) if MANUAL.exists() else []
    by_code = {s["code"]: s for s in stocks}
    picked = {s["code"]: s for s in auto}
    for m in manual:
        base = by_code.get(m["code"], {"code": m["code"], "name": m["name"], "market": None})
        picked.setdefault(m["code"], {**base, "industry_name": done.get(m["code"], {}).get("std_idst_clsf_cd_name"),
                                      "source": "manual", "reason": m.get("reason")})
    result = sorted(picked.values(), key=lambda s: s["code"])
    errors = [c for c, v in done.items() if "error" in v]
    OUT.write_text(json.dumps({"keyword": KEYWORD, "count": len(result), "errors": errors, "stocks": result},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    init_db()
    with connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO stocks(code, name, market, industry_name, source) VALUES (?,?,?,?,?)",
            [(s["code"], s["name"], s.get("market"), s.get("industry_name"), s["source"]) for s in result])
    print(f"반도체 종목 {len(result)}개(자동 {len(auto)}, 수동 보강 {len(result) - len(auto)}), 조회 실패 {len(errors)}개")


if __name__ == "__main__":
    main()
