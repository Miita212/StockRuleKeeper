# D4 Qwen3-8B 모델·채팅 템플릿·라이선스 확인 메모

확인일: 2026-11-04 / 확인자: yappang / 방법: Hugging Face 페이지를 WebFetch로 읽음
(원문 전체가 아니라 페이지 변환본을 요약한 결과다. 라이선스 전문은 아래 URL에서 직접 한 번 더 열어 볼 것.)

## 1. 확인된 것

| 항목 | 내용 | 출처 |
|---|---|---|
| 모델 카드 | https://huggingface.co/Qwen/Qwen3-8B | 모델 카드 |
| 라이선스 | **Apache-2.0** (LICENSE 파일 머리글 "Apache License Version 2.0, January 2004", 저작권자 Alibaba Cloud) | 모델 카드 메타데이터 + LICENSE 파일 |
| 파라미터 | 8.2B (임베딩 제외 6.95B) | 모델 카드 |
| 컨텍스트 | 기본 32,768, YaRN 적용 시 131,072 | 모델 카드 |
| 다국어 | "100+ languages and dialects" 지원이라고만 적혀 있다. **한국어를 특정해 명시하지는 않음** | 모델 카드 |
| 특수 토큰 | eos = `<|im_end|>`, pad = `<|endoftext|>`, `<|im_start|>`=151644, `<|im_end|>`=151645 | tokenizer_config.json |

Apache-2.0 의미(라이선스 전문 기준): 재배포 시 라이선스 사본 첨부, 수정한 파일에는 변경 고지. 파인튜닝한 모델을 배포한다면 이 두 가지를 지킨다.
상업 이용 가능 여부 등 세부 조항은 전문에서 직접 확인하지 않았다.

## 2. 채팅 템플릿

- 형식은 ChatML 계열이다. 메시지는 `<|im_start|>역할 ... <|im_end|>` 로 감싼다.
- 템플릿 본문은 tokenizer_config.json 의 `chat_template`(Jinja2)에 있다. 길어서 이 메모에는 옮기지 않았다.
- 학습 데이터를 만들 때는 직접 문자열을 이어 붙이지 말고 `tokenizer.apply_chat_template(messages, ...)` 로 변환한다. 그래야 학습과 추론의 형식이 같다.
- 메시지 구조 예: `[{"role":"system","content":"..."},{"role":"user","content":"..."}]`

## 3. 사고 모드(thinking) 끄는 법

- 완전히 끄기(하드 스위치): `apply_chat_template(..., enable_thinking=False)`
- 소프트 스위치 `/think`, `/no_think` 는 `enable_thinking=True` 일 때만 의미가 있다.
- 우리 용도(JSON 변환)는 **하드 스위치로 끄는 것**을 기본으로 제안한다. 학습 데이터도 같은 설정으로 변환해야 한다.
- 사고 모드 출력은 `<think>...</think>` 로 감싸진다. 끈 상태에서도 검증 코드가 이 태그가 섞여 나오면 제거/거절하도록 한다. [제안]

## 4. 비사고 모드 권장 샘플링 (모델 카드)

Temperature=0.7, TopP=0.8, TopK=20, MinP=0
→ 단, 우리는 JSON 변환이라 재현성이 중요하다. 평가 때는 temperature 를 낮춰(예: 0) 고정하는 것을 제안한다. [제안, 비교 실험 필요]

## 5. 확인하지 못한 것 (팀 확인 필요)

1. **한국어 금융 용어 이해 수준**: 모델 카드에 한국어 성능 수치가 없다. 용어 진단 시험(T-run)으로 직접 재야 한다.
2. 라이선스 전문 전체(상표, 책임 제한 등)는 직접 읽지 않았다.
3. 4060 8GB에서 4비트 양자화(GGUF Q4_K_M 등) 후 실제 속도·메모리는 측정 전이다.
4. 채팅 템플릿 전체 텍스트는 옮기지 않았다. 학습 코드 작성 시 tokenizer 에서 직접 출력해 확인한다.
