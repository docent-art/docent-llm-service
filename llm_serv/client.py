"""
Run with response = asyncio.run(await internal_client(request, route))

route = "http://localhost:20004/retrieve"
"""
from typing import Any
import httpx
from pydantic import BaseModel

from llm_serv.providers.base import LLMRequest, LLMResponse
from llm_serv.registry import Model


class LLMServiceClient:
    def __init__(self, host:str, port:int):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

        self.provider = None
        self.name = None
                
    async def list_models(self, provider: str | None = None) -> list[dict[str, str]]:
        """
        This method calls the /list_models endpoint of the server.
        It returns a list of models as provider/name pairs available in the server.
        Example:
        [
            {"provider": "AZURE_OPENAI", "name": "gpt-4o"},
            {"provider": "OPENAI", "name": "gpt-4o-mini"},
            {"provider": "AWS", "name": "claude-3-haiku"},
        ]
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/list_models")
            response.raise_for_status()
            models = response.json()
            
            # If provider is specified, filter models by provider
            if provider:
                models = [model for model in models if model["provider"] == provider]
            
            return models

    async def list_providers(self) -> list[str]:
        """
        This method calls the /list_providers endpoint of the server.
        It returns a list of providers available in the server.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/list_providers")
            response.raise_for_status()
            return response.json()

    def set_model(self, provider: str, name: str):
        """
        This method sets the model to be used in the chat method.
        """
        self.provider = provider
        self.name = name

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """
        This method calls the /chat endpoint of the server.
        It returns a LLMResponse object.
        """
        if not self.provider or not self.name:
            raise ValueError("Model is not set, please set it with client.set_model(provider, name) first!")
        
        async with httpx.AsyncClient() as client:            
            request_data = request.model_dump(mode='json')
            
            response = await client.post(
                f"{self.base_url}/chat/{self.provider}/{self.name}",
                json=request_data
            )
            response.raise_for_status()
            return LLMResponse.model_validate(response.json())
        