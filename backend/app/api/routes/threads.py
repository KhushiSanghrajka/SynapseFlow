from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_orchestrator
from app.database import get_db
from app.schemas import ThreadCreate, ThreadRead, ThreadUpdate
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=list[ThreadRead])
def list_threads(
    workflow_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    return svc.list_threads(db, workflow_id=workflow_id)


@router.post("", response_model=ThreadRead, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: ThreadCreate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    try:
        return svc.create_thread(db, payload.workflow_id, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{thread_id}", response_model=ThreadRead)
def update_thread(
    thread_id: str,
    payload: ThreadUpdate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    try:
        return svc.update_thread(db, thread_id, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: str,
    purge_history: bool = Query(default=True),
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    try:
        svc.delete_thread(db, thread_id, clear_history=purge_history)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None

