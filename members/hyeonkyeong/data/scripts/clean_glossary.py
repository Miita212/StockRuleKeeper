"""D1 금융용어사전 정제: 내려받은 파일(CSV, 칸 이름 '용어'와 '설명')에서 HTML 태그를 지우고 glossary_fsc.csv 로 저장한다.

내려받는 일(API 신청, 호출)은 이 스크립트가 하지 않는다. 받은 결과를 용어/설명 두 칸의 CSV로 정리한 뒤 쓴다.

사용: python -I -X utf8 clean_glossary.py 받은파일.csv
"""
import csv
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'glossary_fsc.csv')


def clean(text):
    text = re.sub(r'<br\s*/?>|</p>', '\n', text, flags=re.I)  # 줄바꿈 태그는 줄바꿈으로
    text = re.sub(r'<[^>]+>', '', text)                        # 나머지 태그 삭제
    text = html.unescape(text)                                 # &nbsp; &amp; 등
    return re.sub(r'\s+', ' ', text).strip()


rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8-sig')))
with open(OUT, 'w', encoding='utf-8-sig', newline='') as fp:
    w = csv.writer(fp)
    w.writerow(['용어', '설명'])
    for r in rows:
        w.writerow([clean(r['용어']), clean(r['설명'])])
print(OUT, len(rows), '행')
