from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_orchestrator
from app.database import get_db
from app.schemas import AgentCreate, AgentRead, AgentUpdate
from app.services.orchestrator_service import OrchestratorService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentRead])
def list_agents(db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    return svc.list_agents(db)


@router.get("/capabilities")
def get_capabilities(svc: OrchestratorService = Depends(get_orchestrator)):
    return svc.capabilities()


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    try:
        return svc.create_agent(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(agent_id: str, db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    agent = svc.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


@router.put("/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    svc: OrchestratorService = Depends(get_orchestrator),
):
    agent = svc.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    try:
        return svc.update_agent(db, agent, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, db: Session = Depends(get_db), svc: OrchestratorService = Depends(get_orchestrator)):
    agent = svc.get_agent(db, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    svc.delete_agent(db, agent)
    return None
