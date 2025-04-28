from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.config.database import get_db
from typing import List
import uuid
from src.core.jwt_middleware import (
    get_jwt_token,
    verify_user_client,
)
from src.schemas.schemas import (
    Contact,
    ContactCreate,
)
from src.services import (
    contact_service,
)
import logging

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/contacts",
    tags=["contacts"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=Contact, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to the contact's client
    await verify_user_client(payload, db, contact.client_id)

    return contact_service.create_contact(db, contact)


@router.get("/{client_id}", response_model=List[Contact])
async def read_contacts(
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Verify if the user has access to this client's data
    await verify_user_client(payload, db, client_id)

    return contact_service.get_contacts_by_client(db, client_id, skip, limit)


@router.get("/{contact_id}", response_model=Contact)
async def read_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    db_contact = contact_service.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    # Verify if the user has access to the contact's client
    await verify_user_client(payload, db, db_contact.client_id)

    return db_contact


@router.put("/{contact_id}", response_model=Contact)
async def update_contact(
    contact_id: uuid.UUID,
    contact: ContactCreate,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the current contact
    db_current_contact = contact_service.get_contact(db, contact_id)
    if db_current_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    # Verify if the user has access to the contact's client
    await verify_user_client(payload, db, db_current_contact.client_id)

    # Verify if the user is trying to change the client
    if contact.client_id != db_current_contact.client_id:
        # Verify if the user has access to the new client as well
        await verify_user_client(payload, db, contact.client_id)

    db_contact = contact_service.update_contact(db, contact_id, contact)
    if db_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    return db_contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_jwt_token),
):
    # Get the contact
    db_contact = contact_service.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )

    # Verify if the user has access to the contact's client
    await verify_user_client(payload, db, db_contact.client_id)

    if not contact_service.delete_contact(db, contact_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
