from sqlalchemy.orm import Session
from src.models.models import Agent
from src.schemas.schemas import AgentCreate
from typing import List
import uuid

def get_agent(db: Session, agent_id: uuid.UUID) -> Agent:
    return db.query(Agent).filter(Agent.id == agent_id).first()

def get_agents_by_client(db: Session, client_id: uuid.UUID, skip: int = 0, limit: int = 100) -> List[Agent]:
    return db.query(Agent).filter(Agent.client_id == client_id).offset(skip).limit(limit).all()

def create_agent(db: Session, agent: AgentCreate) -> Agent:
    db_agent = Agent(**agent.model_dump())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

def update_agent(db: Session, agent_id: uuid.UUID, agent: AgentCreate) -> Agent:
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if db_agent:
        for key, value in agent.model_dump().items():
            setattr(db_agent, key, value)
        db.commit()
        db.refresh(db_agent)
    return db_agent

def delete_agent(db: Session, agent_id: uuid.UUID) -> bool:
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if db_agent:
        db.delete(db_agent)
        db.commit()
        return True
    return False 