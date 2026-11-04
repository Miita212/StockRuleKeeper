"""종목코드(6자리) ↔ DART corp_code 매핑. corpCode.xml(zip)을 받아 SQLite corp_codes 표를 만든다."""
import io
import xml.etree.ElementTree as ET
import zipfile

import config
from external.dart.client import get_bytes
from external.fixtures import load


def fetch_corp_codes() -> list[dict]:
    """상장 종목만 [{stock_code, corp_code, corp_name}]로 돌려준다."""
    if config.EXTERNAL_MODE == "fixture":
        return load("dart_corp_codes.json")
    z = zipfile.ZipFile(io.BytesIO(get_bytes("corpCode.xml", {})))
    root = ET.fromstring(z.read(z.namelist()[0]))
    out = []
    for item in root.iter("list"):
        stock_code = (item.findtext("stock_code") or "").strip()
        if stock_code:
            out.append({
                "stock_code": stock_code,
                "corp_code": item.findtext("corp_code").strip(),
                "corp_name": (item.findtext("corp_name") or "").strip(),
            })
    return out
