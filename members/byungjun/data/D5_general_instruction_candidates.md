# 일반 한국어 지시 데이터 후보 (D5)

> 작성: byungjun / 2026-11-04 / 상태: **1차 조사 (웹 검색 결과, 원문 재확인 필요)**
> 용도: 파인튜닝 중 일반 대화 능력을 잃지 않도록 **전체 학습 데이터의 10~20% 이하**로 섞을 공개 데이터를 고른다.
> 한계: 아래 라이선스는 웹 검색에서 확인한 값이다. **크기(행 수)는 확인하지 못했다.** 쓰기 전에 각 Hugging Face 페이지의 라이선스·크기를 직접 확인한다.

## 후보 표

| 후보 | 라이선스 (확인한 값) | 확인 출처 | 주의점 | 잠정 판단 |
| --- | --- | --- | --- | --- |
| `CarrotAI/ko-instruction-dataset` | apache-2.0 | HF 데이터셋 페이지 | 크기·생성 방식 미확인 | **1순위 후보** (생성 방식 확인 후) |
| `nlpai-lab/kullm-v2` | apache-2.0 | HF 데이터셋 카드 | GPT4ALL·Dolly·Vicuna 데이터를 DeepL로 번역한 것. 원본·번역기 이용조건에 따라 사용 제한이 있을 수 있음 | **조건부** (원본 데이터 이용조건 확인 필요) |
| `heegyu/open-korean-instructions` | mit (모음집 저장소 표기) | HF 데이터셋 페이지, GitHub | 여러 데이터를 모은 것이라 **라이선스가 데이터마다 다름**. MIT 표기가 하위 데이터 전체에 적용되는지 불명 | **보류** (쓰려면 하위 데이터별로 확인) |
| KoAlpaca (`beomi/KoAlpaca`, `Bingsu` 등) | 데이터셋 라이선스를 명시한 곳을 찾지 못함 | 검색 결과에 없음 | 라이선스 불명확 | **제외** (확인 전까지 사용 안 함) |

## 사용 원칙
1. 라이선스를 확인하지 못한 자료는 쓰지 않는다 (총괄표 배분 원칙 5).
2. 혼합 비율은 전체의 10~20% 이하. 예: 합성·시드 데이터가 약 3,000개이면 일반 데이터는 300~600개 정도.
3. 일반 데이터도 학습 전에 같은 채팅 형식(system/user/assistant)으로 변환하고, 길이는 학습 토큰 한도(512~1024) 안으로 자른다.
4. 일반 데이터에는 투자 추천·수익 보장 같은 답이 섞여 있을 수 있으니, 가져온 뒤 금지 표현 필터(V7)를 한 번 통과시킨다.

## 직접 확인할 것 (사용 전 체크리스트)
- [ ] 각 후보 HF 페이지의 라이선스 표기와 데이터 크기
- [ ] CarrotAI: 데이터 생성 방식(외부 LLM으로 만들었다면 그 서비스 약관 - D6 참고)
- [ ] KULLM-v2: 원본 3종과 DeepL 번역 결과의 재사용 조건
- [ ] 오픈 모음집은 사용할 하위 데이터를 정한 뒤 그 데이터의 라이선스만 따로 확인

## 출처
- CarrotAI/ko-instruction-dataset (Hugging Face): https://huggingface.co/datasets/CarrotAI/ko-instruction-dataset
- nlpai-lab/kullm-v2 (Hugging Face): https://huggingface.co/datasets/nlpai-lab/kullm-v2
- heegyu/open-korean-instructions (Hugging Face): https://huggingface.co/datasets/heegyu/open-korean-instructions
- HeegyuKim/open-korean-instructions (GitHub): https://github.com/HeegyuKim/open-korean-instructions
