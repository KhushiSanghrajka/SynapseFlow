from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_orchestrator
from app.database import get_db
from app.schemas import (
    CreateWorkflowFromTemplate,
    WorkflowCreate,
    WorkflowRead,
    WorkflowTemplate,
    WorkflowUpdate,
)
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _to_schema(workflow) -> WorkflowRead:
    return WorkflowRead(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        graph=workflow.graph_json,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
    )


@router.get("", response_model=list[WorkflowRead])
def list_workflows(db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    return [_to_schema(workflow) for workflow in svc.list_workflows(db)]


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
    ):
    return _to_schema(svc.create_workflow(db, payload))


@router.get("/templates/library", response_model=list[WorkflowTemplate])
def list_templates(svc: OrchestratorService = Depends(get_orchestrator)):
    return svc.list_templates()


@router.post("/templates/create", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_from_template(
    payload: CreateWorkflowFromTemplate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    try:
        workflow = svc.create_workflow_from_template(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_schema(workflow)


@router.get("/{workflow_id}", response_model=WorkflowRead)
def get_workflow(workflow_id: str, db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    workflow = svc.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return _to_schema(workflow)


@router.put("/{workflow_id}", response_model=WorkflowRead)
def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    workflow = svc.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return _to_schema(svc.update_workflow(db, workflow, payload))


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    workflow = svc.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    svc.delete_workflow(db, workflow)
    return None
