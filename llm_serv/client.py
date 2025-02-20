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
        
        # Do a health check
        try:
            # Create event loop if one doesn't exist
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run health check with 5 second timeout
            health_check_timeout = 5.0
            loop.run_until_complete(self._health_check(health_check_timeout))
        except Exception as e:
            raise ServiceCallException(f"Failed to connect to LLM service at {self.base_url}: {str(e)}")

    async def _health_check(self, timeout: float) -> None:
        """
        Performs a health check by calling the /health endpoint.
        Raises ConnectionError if the server is not healthy or cannot be reached.
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self._default_headers
                )
                
                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("detail", str(error_data))
                    raise ConnectionError(f"Server health check failed: {error_msg}")
                    
                health_data = response.json()
                if health_data.get("status") != "healthy":
                    raise ConnectionError(f"Server reported unhealthy status: {health_data}")
                    
        except httpx.TimeoutException:
            raise ConnectionError(f"Health check timed out after {timeout} seconds")
        except httpx.RequestError as e:
            raise ConnectionError(f"Failed to connect to server: {str(e)}")

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
        This method calls the /list_providers endpoint of the server.
        It returns a list of providers available in the server.

        It raises:
            ServiceCallException - when there is an error retrieving the provider list
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
            TimeoutException - when the request times out
        """
        if not self.provider or not self.name:
            raise ValueError("Model is not set, please set it with client.set_model(provider, name) first!")

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
