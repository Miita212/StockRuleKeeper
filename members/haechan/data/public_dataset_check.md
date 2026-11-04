# D3. 공개 금융 데이터셋 위치·라이선스 확인

작성: haechan / 2026-11-04 / 방법: 웹 검색·페이지 조회 (논문 페이지와 Hugging Face 페이지만 확인, 원문 전체는 읽지 않음)

| 데이터셋 | 위치 | 크기 | 라이선스 (확인된 것) | 사용 가능 여부 |
|---|---|---|---|---|
| ₩ON-Instruct (FINKRX 논문의 학습 데이터) | https://huggingface.co/datasets/KRX-Data/Won-Instruct | 86,007행, 376MB | 데이터셋 카드 license 필드 = **MIT**. 원본 자료는 "공개·무라이선스"라고 적혀 있음 | 학습 참고 가능성 높음. 단, 정답 양식이 우리 JSON과 달라 그대로 학습에 쓰지 않음 |
| FINKRX 논문 | https://aclanthology.org/2025.acl-industry.81 / https://arxiv.org/abs/2503.17963 | - | 논문 자체는 CC BY-NC-SA 4.0 (논문에 대한 권리) | 데이터 라이선스가 아님. 논문 인용 시 출처 표기 |
| KRX-Bench (KRX-Bench-POC 1,002문항) | 논문 각주가 anonymous 저장소(4open.science)를 가리킴. Hugging Face 주소는 **확인 못 함** (amphora/krx-bench-poc 추정 주소는 401 응답) | 1,002문항 | **확인 못 함** | 미확인 → 사용 보류 |
| KFinEval-Pilot | arXiv 2504.13216 (https://arxiv.org/abs/2504.13216). 데이터 다운로드 주소는 논문 페이지에 **없음** | 1,000개 이상 (1,145개라는 2차 출처도 있음) | 논문 페이지에 CC BY-NC-ND 4.0 표시. 데이터 자체 라이선스는 **확인 못 함** | 미확인 → 사용 보류. 파생(ND)·비상업(NC) 제한 가능성 있음 |

## 결론
- 지금 쓸 수 있다고 확인된 것은 **Won-Instruct(MIT)** 하나입니다. 용어 진단(T-a~c)이나 평가 참고용으로만 생각하고, 정답 형식이 다르므로 학습 데이터에 섞지는 않습니다.
- KRX-Bench와 KFinEval-Pilot은 **데이터 위치와 라이선스를 확인하지 못했습니다.** 논문 PDF 부록, 저자 GitHub, Hugging Face 검색으로 추가 확인이 필요합니다.
- "MIT" 표시는 데이터셋 카드의 필드 값입니다. 원본 출처의 저작권까지 보증하는지는 확인하지 않았습니다.

## 남은 확인
1. KRX-Bench, KFinEval-Pilot의 실제 저장소 주소와 라이선스 (논문 부록·저자 GitHub)
2. Won-Instruct의 원본 출처 목록이 상업 이용에 문제없는지 (논문 본문)
3. 우리 프로젝트가 상업 서비스인지 교육용인지 팀 확인 (NC 라이선스 판단에 필요)
