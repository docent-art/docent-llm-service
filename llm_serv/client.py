import httpx

from llm_serv.exceptions import InternalConversionException, ModelNotFoundException, ServiceCallException, ServiceCallThrottlingException, StructuredResponseException
from llm_serv.providers.base import LLMRequest, LLMResponse, LLMResponseFormat


class LLMServiceClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"

        self.provider = None
        self.name = None
        
        # Default headers to accept gzip compression
        self._default_headers = {
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json"
        }

    async def list_models(self, provider: str | None = None) -> list[dict[str, str]]:
        """
        This method calls the /list_models endpoint of the server.
        It returns a list of models as provider/name pairs available in the server.
        Example:
        [
            {"provider": "AZURE_OPENAI", "name": "gpt-4"},
            {"provider": "OPENAI", "name": "gpt-4-mini"},
            {"provider": "AWS", "name": "claude-3-haiku"},
        ]

        It raises:
            ServiceCallException - when there is an error retrieving the model list
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/list_models",
                    headers=self._default_headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("detail", {}).get("message", str(error_data))
                    raise ServiceCallException(f"Failed to list models: {error_msg}")
                    
                return response.json()
        except httpx.RequestError as e:
            raise ServiceCallException(f"Failed to connect to server: {str(e)}")

    async def list_providers(self) -> list[str]:
        """
        This method calls the /list_providers endpoint of the server.
        It returns a list of providers available in the server.

        It raises:
            ServiceCallException - when there is an error retrieving the provider list
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/list_providers",
                    headers=self._default_headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("detail", {}).get("message", str(error_data))
                    raise ServiceCallException(f"Failed to list providers: {error_msg}")
                    
                return response.json()
        except httpx.RequestError as e:
            raise ServiceCallException(f"Failed to connect to server: {str(e)}")

    def set_model(self, provider: str, name: str):
        """
        This method sets the model to be used in the chat method.
        Warning, it does not raise any error!
        """
        self.provider = provider
        self.name = name

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """
        This method calls the /chat endpoint of the server.
        It returns a LLMResponse object.

        It raises:            
            ModelNotFoundException - when the model is not found on the backend
            InternalConversionException - when the internal conversion to the particular provider fails
            ServiceCallException - when the service call fails for any reason
            ServiceCallThrottlingException - when the service call is throttled but the number retries is exhausted
            StructuredResponseException - when the structured response parsing fails
        """
        if not self.provider or not self.name:
            raise ValueError("Model is not set, please set it with client.set_model(provider, name) first!")

        response_class = request.response_class
        response_format = request.response_format

        async with httpx.AsyncClient() as client:
            request_data = request.model_dump(mode="json")

            try:
                response = await client.post(
                    f"{self.base_url}/chat/{self.provider}/{self.name}",
                    json=request_data,
                    headers=self._default_headers
                )
                
                # Handle non-200 responses
                if response.status_code != 200:
                    error_data = response.json()
                    error_type = error_data.get("detail", {}).get("error", "unknown_error")
                    error_msg = error_data.get("detail", {}).get("message", str(error_data))

                    if response.status_code == 404 and error_type == "model_not_found":
                        raise ModelNotFoundException(error_msg)
                    elif response.status_code == 400 and error_type == "internal_conversion_error":
                        raise InternalConversionException(error_msg)
                    elif response.status_code == 429 and error_type == "service_throttling":
                        raise ServiceCallThrottlingException(error_msg)
                    elif response.status_code == 422 and error_type == "structured_response_error":
                        raise StructuredResponseException(
                            error_msg,
                            xml=error_data.get("detail", {}).get("xml", ""),
                            return_class=error_data.get("detail", {}).get("return_class")
                        )
                    elif response.status_code == 502 and error_type == "service_call_error":
                        raise ServiceCallException(error_msg)
                    else:
                        raise ServiceCallException(f"Unexpected error: {error_msg}")

                llm_response_as_json = response.json()
                llm_response = LLMResponse.model_validate(llm_response_as_json)

                # Manually convert to StructuredResponse if needed
                if response_format is LLMResponseFormat.XML and response_class is not str:
                    llm_response.output = response_class.from_text(llm_response.output)

                return llm_response

            except httpx.RequestError as e:
                raise ServiceCallException(f"Failed to connect to server: {str(e)}")
