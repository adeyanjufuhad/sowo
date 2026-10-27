from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vendor
from app.services import auth
from app.services.ollama import ChatModel, get_ollama_client


def get_chat_model() -> ChatModel:
    """The model behind the agent. Tests replace this with a scripted stand-in."""
    return get_ollama_client()


ChatModelDependency = Annotated[ChatModel, Depends(get_chat_model)]

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="Sign in to continue", headers={"WWW-Authenticate": "Bearer"})


def get_session_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> str:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    return credentials.credentials


def get_current_vendor(
    token: Annotated[str, Depends(get_session_token)], session: Annotated[Session, Depends(get_db)]
) -> Vendor:
    """The signed-in vendor, from `Authorization: Bearer <session token>`. Every dashboard route needs this."""
    vendor = auth.find_vendor(session, token)
    if vendor is None:
        raise _unauthorized()
    return vendor


CurrentVendor = Annotated[Vendor, Depends(get_current_vendor)]
