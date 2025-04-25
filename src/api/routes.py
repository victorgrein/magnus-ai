from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from src.config.database import get_db
from src.schemas.schemas import (
    Client, ClientCreate,
    Contact, ContactCreate,
    Agent, AgentCreate,
    Message, MessageCreate
)
from src.services import (
    client_service,
    contact_service,
    agent_service,
    message_service
)
from src.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from src.services.agent_runner import run_agent
from src.core.exceptions import AgentNotFoundError, InternalServerError
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions import DatabaseSessionService
from src.config.settings import settings

router = APIRouter()

# Configuração do PostgreSQL
POSTGRES_CONNECTION_STRING = settings.POSTGRES_CONNECTION_STRING

# Inicializar os serviços globalmente
session_service = DatabaseSessionService(db_url=POSTGRES_CONNECTION_STRING)
artifacts_service = InMemoryArtifactService()

@router.post("/chat", response_model=ChatResponse, responses={
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        final_response_text = await run_agent(
            request.agent_id, 
            request.contact_id,
            request.message, 
            session_service, 
            artifacts_service,
            db
        )
        
        return {
            "response": final_response_text,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }

    except AgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Rotas para Clientes
@router.post("/clients/", response_model=Client)
def create_client(client: ClientCreate, db: Session = Depends(get_db)):
    return client_service.create_client(db, client)

@router.get("/clients/", response_model=List[Client])
def read_clients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return client_service.get_clients(db, skip, limit)

@router.get("/clients/{client_id}", response_model=Client)
def read_client(client_id: uuid.UUID, db: Session = Depends(get_db)):
    db_client = client_service.get_client(db, client_id)
    if db_client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return db_client

@router.put("/clients/{client_id}", response_model=Client)
def update_client(client_id: uuid.UUID, client: ClientCreate, db: Session = Depends(get_db)):
    db_client = client_service.update_client(db, client_id, client)
    if db_client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return db_client

@router.delete("/clients/{client_id}")
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db)):
    if not client_service.delete_client(db, client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted successfully"}

# Rotas para Contatos
@router.post("/contacts/", response_model=Contact)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db)):
    return contact_service.create_contact(db, contact)

@router.get("/contacts/{client_id}", response_model=List[Contact])
def read_contacts(client_id: uuid.UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return contact_service.get_contacts_by_client(db, client_id, skip, limit)

@router.get("/contact/{contact_id}", response_model=Contact)
def read_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    db_contact = contact_service.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.put("/contact/{contact_id}", response_model=Contact)
def update_contact(contact_id: uuid.UUID, contact: ContactCreate, db: Session = Depends(get_db)):
    db_contact = contact_service.update_contact(db, contact_id, contact)
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@router.delete("/contact/{contact_id}")
def delete_contact(contact_id: uuid.UUID, db: Session = Depends(get_db)):
    if not contact_service.delete_contact(db, contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact deleted successfully"}

# Rotas para Agentes
@router.post("/agents/", response_model=Agent)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    return agent_service.create_agent(db, agent)

@router.get("/agents/{client_id}", response_model=List[Agent])
def read_agents(client_id: uuid.UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return agent_service.get_agents_by_client(db, client_id, skip, limit)

@router.get("/agent/{agent_id}", response_model=Agent)
def read_agent(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    db_agent = agent_service.get_agent(db, agent_id)
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db_agent

@router.put("/agent/{agent_id}", response_model=Agent)
def update_agent(agent_id: uuid.UUID, agent: AgentCreate, db: Session = Depends(get_db)):
    db_agent = agent_service.update_agent(db, agent_id, agent)
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db_agent

@router.delete("/agent/{agent_id}")
def delete_agent(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    if not agent_service.delete_agent(db, agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted successfully"}

# Rotas para Mensagens
@router.post("/messages/", response_model=Message)
def create_message(message: MessageCreate, db: Session = Depends(get_db)):
    return message_service.create_message(db, message)

@router.get("/messages/{session_id}", response_model=List[Message])
def read_messages(session_id: uuid.UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return message_service.get_messages_by_session(db, session_id, skip, limit)

@router.get("/message/{message_id}", response_model=Message)
def read_message(message_id: int, db: Session = Depends(get_db)):
    db_message = message_service.get_message(db, message_id)
    if db_message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return db_message

@router.put("/message/{message_id}", response_model=Message)
def update_message(message_id: int, message: MessageCreate, db: Session = Depends(get_db)):
    db_message = message_service.update_message(db, message_id, message)
    if db_message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return db_message

@router.delete("/message/{message_id}")
def delete_message(message_id: int, db: Session = Depends(get_db)):
    if not message_service.delete_message(db, message_id):
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message deleted successfully"} 