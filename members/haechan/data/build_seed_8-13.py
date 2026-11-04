"""H4-b 시드(지표 8~13 중심) 만들기. 성장성(8,9), 가치(10,11), 배당(12,13).

실행: python -X utf8 build_seed_8-13.py   (같은 폴더에 seed_8-13.jsonl 생성)
검증: python -X utf8 validate_data.py --master-dir ../../byungjun/data --input seed_8-13.jsonl

정답 규칙은 build_seed_1-7.py 와 같다(그 파일 머리말 참고). 이 구간에서 새로 정한 것 [제안, 팀 확인 필요]
- "싸다/저평가/싼 주식"은 PER·PBR로 갈리므로 되묻기. H3-0 6장 '싼/저평가' 묶음은 10·11·16 이다.
- "성장하는 회사/실적이 좋아지는 회사"는 매출액 증가율(8)·영업이익 증가율(9)로 갈려 되묻기.
- "배당 꾸준한 곳"은 금액(12)인지 연속(13)인지 모호해 되묻기(yappang 사전 메모, H3-0 6장 '배당' 묶음).
  시트 예시 E06은 이 말을 12·13 확정으로 적었지만, H3-0 T1(값이 없으면 되묻기)을 따랐다.
- 증가율에서 "N배 늘었다"는 증가율 (N-1)×100% 로 환산한다 (두 배 = 100%).
- 이하 <= / 미만 < / 이상 >= / 초과·넘는 > 를 구분한다(byungjun 의 같은 방향 두 부등호 허용, cfc5d2c 이후).
- 적자 전환·흑자 전환 영업이익 증가율은 처리 규칙이 없어 시드에 넣지 않았다(마스터 note 참고).
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("seed17", HERE / "build_seed_1-7.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

ind, confirm, clarify_value, ambiguous, refuse = S.ind, S.confirm, S.clarify_value, S.ambiguous, S.refuse

CHEAP = ambiguous("싸다고 볼 수 있는 기준이 여러 가지예요. 어떤 걸로 볼까요?", [10, 11, 16])
CHEAP2 = ambiguous("싸다고 볼 수 있는 기준이 두 가지예요. 어떤 걸로 볼까요?", [10, 11])
GROW = ambiguous("성장은 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [8, 9])
PERF = ambiguous("실적이 좋아진다는 건 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [8, 9])
BIGGER = ambiguous("커진다는 건 여러 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [8, 14])
BUBBLE = ambiguous("거품은 여러 지표로 볼 수 있어요. 어떤 걸로 볼까요?", [10, 11, 15])
DIV = ambiguous("배당은 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [12, 13])
DIV_STEADY = ambiguous("꾸준한 배당은 두 가지로 볼 수 있어요. 어떤 걸로 볼까요?", [12, 13])


def no_metric(name, hint):
    return refuse(f"{name}는 아직 쓰지 않는 지표예요. {hint}")


SEEDS = [
    # ---- 8 매출액 증가율 (>= %)
    ("단일", "매출액 증가율 15% 이상인 회사", confirm(ind(8, 15)), "확정"),
    ("단일", "작년보다 매출이 20% 넘게 늘어난 회사", confirm(ind(8, 20, ">")), "'넘게' = 초과(>)"),
    ("단일", "매출액 증가율 20% 이상인 회사", confirm(ind(8, 20)), "'이상' = >="),
    ("단일", "작년보다 매출이 두 배 이상 늘어난 회사", confirm(ind(8, 100)), "두 배 = 증가율 100%"),
    ("단일", "매출이 줄어드는 회사는 싫어요", confirm(ind(8, 0)), "줄지 않음 → >= 0 (yappang 사전 '반대 방향')"),
    ("되묻기(값 없음)", "매출이 쑥쑥 크는 회사가 좋아", clarify_value(8), "비유 표현"),
    ("되묻기(값 없음) + 오타", "매출 늘어나는 회사만 볼래여", clarify_value(8), "오타·말투"),
    ("되묻기(값 없음)", "작년보다 더 많이 파는 회사", clarify_value(8), "상황설명"),
    # ---- 9 영업이익 증가율 (>= %)
    ("단일", "영업이익 증가율 10% 이상인 회사", confirm(ind(9, 10)), "확정"),
    ("단일", "본업 이익이 작년보다 30% 이상 늘어난 회사", confirm(ind(9, 30)), "확정"),
    ("단일", "영업이익이 줄어드는 회사는 빼줘", confirm(ind(9, 0)), "줄지 않음 → >= 0"),
    ("되묻기(값 없음)", "본업 이익이 늘어나는 회사가 좋아요", clarify_value(9), "일상어"),
    ("되묻기(값 없음)", "이익이 늘어나는 속도가 빠른 회사", clarify_value(9), "상황설명"),
    ("되묻기(값 없음) + 오타", "영업이익 성장율 높은 회사", clarify_value(9), "'성장율' 표기 오류"),
    # ---- 8·9 모호
    ("되묻기(지표 모호)", "성장하는 회사가 좋아요", GROW, "yappang 사전: 포괄 표현(8·9)"),
    ("되묻기(지표 모호) + 오타", "성장하는회사 위주로 볼래여", GROW, "같은 정답, 오타"),
    ("되묻기(지표 모호)", "실적이 좋아지는 회사", PERF, "yappang 사전: 실적=매출/이익 모호"),
    ("되묻기(지표 모호)", "덩치가 커지는 회사", BIGGER, "yappang 사전: 시가총액(14)과도 겹침"),
    # ---- 10 PER (<= 배)
    ("단일", "PER 10배 이하인 주식", confirm(ind(10, 10)), "확정"),
    ("단일", "PER 10배 미만인 주식", confirm(ind(10, 10, "<")), "'미만' = <"),
    ("단일", "PER 20배 넘는 주식은 싫어", confirm(ind(10, 20)), "'넘는 건 제외' → <= 20"),
    ("단일", "번 돈에 비해 주가가 15배를 안 넘는 주식", confirm(ind(10, 15)), "이익 대비 주가 = PER"),
    ("단일 + 오타", "피이알 8배 이하 회사만 볼래요", confirm(ind(10, 8)), "소리 나는 대로 쓴 표기"),
    ("되묻기(값 없음)", "PER 낮은 주식이 좋아", clarify_value(10), "값 없음"),
    ("되묻기(값 없음)", "이익 대비 싼 주식", clarify_value(10), "상황설명"),
    ("되묻기(값 없음)", "버는 돈에 비해 비싸지 않은 주식", clarify_value(10), "상황설명"),
    ("되묻기(값 없음) + 오타", "이익에 비해 주가 높은 주식은 시러", clarify_value(10), "오타·반말, 비싼 쪽을 피함"),
    # ---- 11 PBR (<= 배)
    ("단일", "PBR 1배 이하인 주식", confirm(ind(11, 1)), "yappang 사전 값 포함 표현"),
    ("단일", "PBR 0.8배 이하 회사", confirm(ind(11, 0.8)), "소수 값"),
    ("단일", "장부가보다 싼 주식", confirm(ind(11, 1)), "장부가(순자산)보다 싸다 = PBR 1배 이하"),
    ("단일", "청산가치보다 싼 주식", confirm(ind(11, 1)), "순자산보다 낮은 가격 = PBR 1배 이하"),
    ("되묻기(값 없음)", "PBR 낮은 주식이 좋아요", clarify_value(11), "값 없음"),
    ("되묻기(값 없음)", "순자산 대비 주가가 낮은 주식", clarify_value(11), "상황설명"),
    ("되묻기(값 없음) + 오타", "자산에 비해 싼 회사만 볼래여", clarify_value(11), "오타·말투"),
    # ---- 10·11 모호
    ("되묻기(지표 모호)", "싼 주식이 좋아요", CHEAP, "H3-0 6장 '싼/저평가' 묶음(10·11·16)"),
    ("되묻기(지표 모호) + 오타", "싼 주식 위주로 볼래여", CHEAP, "같은 정답, 오타"),
    ("되묻기(지표 모호)", "저평가된 주식 찾아줘", CHEAP2, "yappang 사전: 저평가=PER·PBR 둘 다 가능"),
    ("되묻기(지표 모호)", "비싼 주식은 피하고 싶어", CHEAP, "싼/비싼 묶음"),
    ("되묻기(지표 모호)", "거품 낀 주식은 싫어요", BUBBLE, "yappang 사전: 11·15 와 겹침"),
    # ---- 12 배당수익률 (>= %)
    ("단일", "배당수익률 4% 이상인 종목", confirm(ind(12, 4)), "확정"),
    ("단일", "배당을 주가의 3% 넘게 주는 회사", confirm(ind(12, 3, ">")), "'3% 넘게' = 초과(>)"),
    ("되묻기(값 없음)", "배당 잘 주는 회사가 좋아", clarify_value(12), "일상어"),
    ("되묻기(값 없음)", "고배당주 위주로 보고 싶어요", clarify_value(12), "약어"),
    ("되묻기(값 없음) + 오타", "배당 마니 주는 회사", clarify_value(12), "오타"),
    ("되묻기(값 없음)", "용돈 주는 주식이 좋아", clarify_value(12), "비유"),
    ("되묻기(값 없음)", "배당률 높은 주식", clarify_value(12), "값 없음"),
    # ---- 13 연속 배당 연수 (>= 년)
    ("단일", "5년 연속 배당하는 회사", confirm(ind(13, 5)), "확정"),
    ("단일", "3년 연속 배당을 준 회사만", confirm(ind(13, 3)), "확정"),
    ("되묻기(값 없음)", "배당을 한 해도 안 거른 회사", clarify_value(13), "연수 값 없음"),
    ("되묻기(값 없음)", "배당 끊긴 적 없는 회사가 좋아요", clarify_value(13), "부정형"),
    ("되묻기(값 없음) + 오타", "매년 꼬박꼬박 배당하는회사", clarify_value(13), "띄어쓰기 오류"),
    # ---- 12·13 모호
    ("되묻기(지표 모호)", "배당 꾸준한 곳이 좋아", DIV_STEADY, "꾸준=금액인지 연속인지 모호. E06(확정)과 다르게 H3-0 T1·T2 를 따름"),
    ("되묻기(지표 모호)", "배당으로 수익 내고 싶어", DIV, "yappang 사전: 12·13 겹침"),
    ("되묻기(지표 모호)", "장기 배당주 위주로 보고 싶어요", DIV, "yappang 사전: 12 와 겹침"),
    # ---- 복수 지표 확정
    ("복수", "PER 10배 이하이고 PBR 1배 이하인 주식", confirm(ind(10, 10), ind(11, 1)), "지표 2개"),
    ("복수", "매출액 증가율 15% 이상이고 영업이익 증가율 10% 이상인 회사",
     confirm(ind(8, 15), ind(9, 10)), "지표 2개"),
    ("복수", "배당수익률 3% 이상이고 5년 연속 배당하는 회사", confirm(ind(12, 3), ind(13, 5)), "지표 2개"),
    ("복수", "PBR 1배 이하이면서 배당수익률 2% 이상인 주식", confirm(ind(11, 1), ind(12, 2)), "지표 2개"),
    ("복수", "PER 10배 이하, 매출 20% 이상 성장, 3년 연속 배당하는 회사",
     confirm(ind(10, 10), ind(8, 20), ind(13, 3)), "지표 3개"),
    ("복수(영역 섞임)", "부채비율 100% 이하이고 PER 10배 이하인 주식", confirm(ind(1, 100), ind(10, 10)), "1~7 영역과 섞임"),
    ("복수(영역 섞임)", "3년 연속 흑자이고 배당수익률 2% 이상인 회사", confirm(ind(6, 3), ind(12, 2)), "1~7 영역과 섞임"),
    # ---- 거절
    ("거절", "PSR 낮은 주식 찾아줘", no_metric("PSR", "싸다는 건 PER이나 PBR로 볼 수 있어요."), "20개 밖 지표"),
    ("거절", "배당성향 높은 회사만 보여줘",
     no_metric("배당성향", "배당은 배당수익률이나 연속 배당 연수로 볼 수 있어요."), "20개 밖 지표"),
    ("거절", "EV/EBITDA 낮은 회사를 알려줘", no_metric("EV/EBITDA", "싸다는 건 PER이나 PBR로 볼 수 있어요."), "20개 밖 지표"),
    ("거절", "저평가 종목 딱 하나만 찍어줘", refuse(S.NO_PICK), "종목 추천 요청"),
    ("거절", "이 주식 배당 받으려고 지금 사도 돼?", refuse(S.NO_PICK), "종목 추천 요청"),
]


def main():
    out = HERE / "seed_8-13.jsonl"
    lines = []
    for n, (kind, user, answer, note) in enumerate(SEEDS, 1):
        ids = set(answer.get("anchors", []))
        if "indicator_id" in answer:
            ids.add(answer["indicator_id"])
        ids |= {c["id"] for c in answer.get("candidates", [])}
        lines.append(json.dumps({
            "type": "SEED", "seed_id": f"H4b-{n:03d}", "kind": kind, "note": note, "indicator_ids": sorted(ids),
            "messages": [{"role": "system", "content": S.SYSTEM}, {"role": "user", "content": user},
                         {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}],
        }, ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    kinds = {}
    for k, *_ in SEEDS:
        kinds[k.split(" + ")[0]] = kinds.get(k.split(" + ")[0], 0) + 1
    print(f"{len(lines)}개 저장: {out}")
    print("유형별:", kinds)


if __name__ == "__main__":
    main()
