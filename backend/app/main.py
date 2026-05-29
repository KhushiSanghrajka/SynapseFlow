from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.database import init_db
from app.logging_setup import setup_logging
from app.runtime.log_bus import LogBus
from app.services.orchestrator_service import OrchestratorService
from app.services.telegram_service import TelegramBridge

settings = get_settings()
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log_bus = LogBus()
    orchestrator = OrchestratorService(settings, log_bus)
    orchestrator.seed_demo_data()
    telegram_bridge = TelegramBridge(settings, orchestrator)
    telegram_bridge.start()

    app.state.orchestrator = orchestrator
    app.state.telegram_bridge = telegram_bridge
    yield
    telegram_bridge.stop()


app = FastAPI(
    title=settings.app_name,
    description="Visual AI agent workflow orchestration platform with Telegram integration and live monitoring.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins
    + [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://0.0.0.0:5173",
    ],
    allow_origin_regex=r"^https?://([a-zA-Z0-9\.-]+|localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}
