from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import get_orchestrator
from app.database import get_db
from app.schemas import LogEventRead, MessageRead
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/executions/{execution_id}/logs", response_model=list[LogEventRead])
def get_execution_logs(
    execution_id: str,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    return svc.get_logs(db, execution_id)


@router.get("/executions/{execution_id}/messages", response_model=list[MessageRead])
def get_execution_messages(
    execution_id: str,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    return svc.get_messages(db, execution_id)


@router.get("/summary")
def get_summary(db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    return svc.monitoring_summary(db)


@router.delete("/history")
def clear_history(
    thread_id: str | None = None,
    workflow_id: str | None = None,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    cleared = svc.clear_history(db, thread_id=thread_id, workflow_id=workflow_id)
    return {"cleared_executions": cleared}


@router.websocket("/ws/live")
async def monitoring_ws(websocket: WebSocket):
    svc: OrchestratorService = websocket.app.state.orchestrator
    await svc.log_bus.connect(websocket)
    try:
        while True:
            # Keep connection alive; we currently only push server-side events.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await svc.log_bus.disconnect(websocket)
    except Exception:
        await svc.log_bus.disconnect(websocket)
