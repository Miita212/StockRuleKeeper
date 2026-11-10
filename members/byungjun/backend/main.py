"""FastAPI 서버. 실행: uvicorn main:app --host 0.0.0.0 --port 8000 (backend 폴더에서)

앱은 이 서버만 부른다. 외부 API 키는 서버 .env 에만 있다.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from api import principles, simulation, stocks
from db.database import init_db
from services import price_refresh
from services.live import seed_stocks


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_stocks()  # stocks 표가 비어 있으면 종목 풀 파일로 채운다
    price_refresh.start()  # 장 마감 뒤 DB 가격 자동 갱신(백그라운드)
    yield


app = FastAPI(title="StockRuleKeeper", lifespan=lifespan)
# 개발·시연용: 앱(웹뷰)이 다른 주소에서 부르므로 모두 허용한다
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(principles.router)
app.include_router(stocks.router)
app.include_router(simulation.router)

# 가상 주식앱(정적 웹 1장): http://서버주소:8000/virtual-app/
VIRTUAL_APP = Path(__file__).parent.parent / "virtual-app"
if VIRTUAL_APP.exists():
    app.mount("/virtual-app", StaticFiles(directory=VIRTUAL_APP, html=True), name="virtual-app")


@app.get("/health")
def health():
    return {"ok": True, "mode": config.EXTERNAL_MODE, "llm": config.LLM_PROVIDER, "user": config.FIXED_USER_ID}
