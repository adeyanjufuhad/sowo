from typing import Annotated

from fastapi import Depends

from app.services.ollama import ChatModel, get_ollama_client


def get_chat_model() -> ChatModel:
    """The model behind the agent. Tests replace this with a scripted stand-in."""
    return get_ollama_client()


ChatModelDependency = Annotated[ChatModel, Depends(get_chat_model)]
