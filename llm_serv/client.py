import httpx
import asyncio

from llm_serv.exceptions import InternalConversionException, ModelNotFoundException, ServiceCallException, ServiceCallThrottlingException, StructuredResponseException, TimeoutException
from llm_serv.providers.base import LLMRequest, LLMResponse, LLMResponseFormat


class LLMServiceClient:
    def __init__(self, host: str, port: int, timeout: float = 60.0):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        
        self.provider = None
        self.name = None
        
        # Default headers to accept gzip compression
        self._default_headers = {
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json"
        }

    def validate_timeout(self, timeout: float) -> float:
        """
        Enforce a minimum timeout of 1 second.
        """
        return 1 if timeout <= 0 else timeout

    async def server_health_check(self, timeout: float = 5.0) -> None:
        """
        Performs a health check by calling the /health endpoint of the server.
        Should be called immediately after construction when in an async context.
        It does NOT test models, only the server itself.
        
        Args:
            timeout: Maximum time to wait for health check response in seconds
            
        Raises:
            ServiceCallException: If the server is not healthy or cannot be reached
        """
        timeout = self.validate_timeout(timeout)
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self._default_headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("detail", str(error_data))
                    raise ServiceCallException(f"Server health check failed: {error_msg}")
                    
                health_data = response.json()
                if health_data.get("status") != "healthy":
                    raise ServiceCallException(f"Server reported unhealthy status: {health_data}")
                    
        except httpx.TimeoutException:
            raise ServiceCallException(f"Health check timed out after {timeout} seconds")
        except httpx.RequestError as e:
            raise ServiceCallException(f"Failed to connect to server: {str(e)}")

    async def list_models(self, provider: str | None = None) -> list[dict[str, str]]:
        """
        Lists all available models from the server.
        
        Args:
            provider: Optional provider name to filter models
        
        Returns:
            list[dict[str, str]]: List of models as provider/name pairs.
            Example:
            [
                {"provider": "AZURE_OPENAI", "name": "gpt-4"},
                {"provider": "OPENAI", "name": "gpt-4-mini"},
                {"provider": "AWS", "name": "claude-3-haiku"},
            ]

        Raises:
            ServiceCallException: When there is an error retrieving the model list
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
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
        Lists all available providers from the server.

        Returns:
            list[str]: List of provider names

        Raises:
            ServiceCallException: When there is an error retrieving the provider list
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
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
        Sets the model to be used in subsequent chat requests.
        
        Args:
            provider: Provider name (e.g., "AWS", "AZURE")
            name: Model name (e.g., "claude-3-haiku", "gpt-4")
        """
        self.provider = provider
        self.name = name

    async def chat(self, request: LLMRequest, timeout: float | None = None) -> LLMResponse:
        """
        Sends a chat request to the server.

        Args:
            request: LLMRequest object containing the conversation and parameters

        Returns:
            LLMResponse: Server response containing the model output

        Raises:            
            ValueError: When model is not set
            ModelNotFoundException: When the model is not found on the backend
            InternalConversionException: When the internal conversion to the particular provider fails
            ServiceCallException: When the service call fails for any reason
            ServiceCallThrottlingException: When the service call is throttled but the number retries is exhausted
            StructuredResponseException: When the structured response parsing fails
            TimeoutException: When the request times out
        """
        if not self.provider or not self.name:
            raise ValueError("Model is not set, please set it with client.set_model(provider, name) first!")
        
        timeout = self.timeout if timeout is None else self.validate_timeout(timeout)
            
        response_class = request.response_class
        response_format = request.response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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

            except httpx.TimeoutException as e:
                raise TimeoutException(f"Request timed out after {self.timeout} seconds") from e
            except httpx.RequestError as e:
                if isinstance(e, httpx.ReadTimeout):
                    raise TimeoutException(f"Read timeout after {self.timeout} seconds") from e
                raise ServiceCallException(f"Failed to connect to server: {str(e)}")

    async def model_health_check(self, timeout: float = 5.0) -> bool:
        """
        Performs a quick test of the LLM by sending a simple message.
        Should be called after setting a model to verify it's working.
        
        Args:
            timeout: Maximum time to wait for test response in seconds
            
        Returns:
            bool: True if test was successful
            
        Raises:
            ValueError: If model is not set
            ServiceCallException: If the test fails for any reason
            TimeoutException: If the request times out
        """
        if not self.provider or not self.name:
            raise ValueError("Model is not set, please set it with client.set_model(provider, name) first!")

        timeout = self.validate_timeout(timeout)
        
        try:
            # Create a minimal test conversation
            from llm_serv.conversation.conversation import Conversation
            from llm_serv.providers.base import LLMRequest
            
            request = LLMRequest(
                conversation=Conversation.from_prompt("1+1="),
                max_completion_tokens=5,
                temperature=0.0
            )
            
            response = await self.chat(request, timeout=timeout)
            return True
                
        except Exception as e:
            # Preserve the original exception type if it's one we already handle
            if isinstance(e, (ServiceCallException, TimeoutException)):
                raise
            # Wrap other exceptions in ServiceCallException
            raise ServiceCallException(f"Model test failed: {str(e)}") from e
    