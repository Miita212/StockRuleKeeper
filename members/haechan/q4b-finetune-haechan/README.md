# 4B(Qwen3-4B) 파인튜닝 — haechan 실행분 (2026-11-09)

yappang 님이 준 fixed-4 데이터와 스크립트로 이 PC(RTX 4060 노트북)에서 학습·평가한 기록입니다.

- `scripts/` 학습·평가 스크립트 (yappang 인수인계본. `train_qlora.py`는 저장소 최신본과 fixed 파일명 검사 한 줄만 다름)
- `results/` 평가 결과(공식 111, haechan 123), 학습 데이터 해시, 보고서 `REPORT-v4.md`
- `logs/` 학습 로그, 평가 로그, 시험 학습 로그
- `data-info/` 데이터 버전·해시·시험 세트 설명 (데이터 파일 자체는 yappang 폴더에 있어 올리지 않음)
- 어댑터 가중치(약 252MB)는 팀 규칙에 따라 저장소에 올리지 않음. 필요하면 haechan 에게 직접 요청

전체 과정(v1~v7, 4B)은 `../training-results-haechan/결과보고서-v1-v7-4B.md`
