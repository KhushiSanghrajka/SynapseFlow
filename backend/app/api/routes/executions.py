from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_orchestrator
from app.database import get_db
from app.schemas import ExecutionCreate, ExecutionRead
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=list[ExecutionRead])
def list_executions(db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    return svc.list_executions(db)


@router.post("", response_model=ExecutionRead, status_code=status.HTTP_202_ACCEPTED)
async def start_execution(
    payload: ExecutionCreate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    try:
        return await svc.start_execution(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{execution_id}", response_model=ExecutionRead)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    record = svc.get_execution(db, execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Execution not found.")
    return record

