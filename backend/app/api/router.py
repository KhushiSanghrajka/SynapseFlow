from fastapi import APIRouter

from app.api.routes import agents, executions, monitoring, threads, workflows

api_router = APIRouter()
api_router.include_router(agents.router)
api_router.include_router(workflows.router)
api_router.include_router(executions.router)
api_router.include_router(monitoring.router)
api_router.include_router(threads.router)
