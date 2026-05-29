from fastapi import Request

from app.services.orchestrator_service import OrchestratorService


def get_orchestrator(request: Request) -> OrchestratorService:
    return request.app.state.orchestrator

