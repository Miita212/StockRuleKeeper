"""fixture 모드용 샘플 로더. 값은 모두 가짜이고 응답 구조만 실제를 따른다."""
import json

import config


def load(name: str):
    return json.loads((config.FIXTURE_DIR / name).read_text(encoding="utf-8"))
