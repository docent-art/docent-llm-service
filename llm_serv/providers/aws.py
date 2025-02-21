import os

import boto3
from dotenv import load_dotenv
from pydantic import Field
from rich import print
from tenacity import retry, stop_after_attempt, wait_exponential

from llm_serv.conversation.conversation import Conversation
from llm_serv.conversation.role import Role
from llm_serv.exceptions import CredentialsException, InternalConversionException, ServiceCallException, ServiceCallThrottlingException
from llm_serv.providers.base import LLMRequest, LLMResponseFormat, LLMService, LLMTokens
from llm_serv.registry import Model
from llm_serv.structured_response.model import StructuredResponse


def check_credentials() -> None:
    required_variables = ["AWS_DEFAULT_REGION", "AWS_SECRET_ACCESS_KEY", "AWS_ACCESS_KEY_ID"]
    
    missing_vars = []
    for var in required_variables:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise CredentialsException(
            f"Missing required environment variables for AWS: {', '.join(missing_vars)}"
        )


class AWSLLMService(LLMService):
    def __init__(self, model: Model):
        super().__init__(model)

        self._context_window = model.max_tokens
        self._model_max_tokens = model.max_output_tokens

        from botocore.config import Config

        config = Config(retries={"max_attempts": 5, "mode": "adaptive"})

        self._client = boto3.session.Session(region_name=os.getenv("AWS_DEFAULT_REGION")).client(
            service_name="bedrock-runtime",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            config=config,
        )

    def _convert(self, request: LLMRequest) -> tuple[list, dict, dict]:
        """
        Ref here: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse.html
        returns (messages, system, config)

        Example of response:
        response = client.converse(
            modelId='string',
            messages=[
                {
                    'role': 'user'|'assistant',
                    'content': [
                        {
                            'text': 'string',
                            'image': {
                                'format': 'png'|'jpeg'|'gif'|'webp',
                                'source': {
                                    'bytes': b'bytes'
                                }
                            },
                            'document': {
                                'format': 'pdf'|'csv'|'doc'|'docx'|'xls'|'xlsx'|'html'|'txt'|'md',
                                'name': 'string',
                                'source': {
                                    'bytes': b'bytes'
                                }
                            },


        You can include up to 20 images. Each image's size, height, and width must be no more than 3.75 MB, 8000 px, and 8000 px, respectively.
        You can include up to five documents. Each document's size must be no more than 4.5 MB.
        If you include a ContentBlock with a document field in the array, you must also include a ContentBlock with a text field.
        You can only include images and documents if the role is user.
        """
        try:
            messages = []
            for message in request.conversation.messages:
                _message = {"role": message.role.value}
                _content = []

                # Only user messages can contain images and documents
                # has_attachments = bool(message.images or message.documents)
                # if has_attachments and message.role != Role.USER:
                #    raise ValueError(f"Images and documents can only be included in user messages, not {message.role}")

                if message.text:
                    _content.append({"text": message.text})

                """if message.images:
                    # Check image count limit
                    if len(message.images) > 20:
                        raise ValueError(f"Maximum of 20 images allowed per message, got {len(message.images)}")
                    
                    for image in message.images:
                        # Check image size limit (3.75 MB = 3,932,160 bytes)
                        image_bytes = image._pil_to_bytes(image.image)
                        if len(image_bytes) > 3_932_160:
                            raise ValueError(f"Image size must be under 3.75 MB, got {len(image_bytes)/1_048_576:.2f} MB")
                        
                        # Check image dimensions
                        if image.width > 8000 or image.height > 8000:
                            raise ValueError(f"Image dimensions must be under 8000x8000 pixels, got {image.width}x{image.height}")
                        
                        _content.append({
                            "image": {
                                "format": image.format or "png",
                                "source": {
                                    "bytes": image_bytes
                                }
                            }
                        })
                
                if message.documents:
                    # Check document count limit
                    if len(message.documents) > 5:
                        raise ValueError(f"Maximum of 5 documents allowed per message, got {len(message.documents)}")
                    
                    # Check if there's a text content when documents are present
                    if not any(c.get("text") for c in _content):
                        raise ValueError("A text field is required when including documents")
                    
                    for document in message.documents:
                        # Check document size limit (4.5 MB = 4,718,592 bytes)
                        if len(document.content) > 4_718_592:
                            raise ValueError(f"Document size must be under 4.5 MB, got {len(document.content)/1_048_576:.2f} MB")
                        
                        _content.append({
                            "document": {
                                "format": document.extension,
                                "name": document.name or "",
                                "source": {
                                    "bytes": document.content
                                }
                            }
                        })
                """

                _message["content"] = _content
                messages.append(_message)

            system = (
                [
                    {
                        "text": request.conversation.system,
                    }
                ]
                if request.conversation.system is not None and len(request.conversation.system) > 0
                else None
            )

            config = {
                "maxTokens": request.max_completion_tokens,
                "temperature": request.temperature,
                "topP": request.top_p,
            }

            return messages, system, config
        except Exception as e:
            raise InternalConversionException(f"Failed to convert request for AWS: {str(e)}") from e

    @retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=3, max=60))
    def _service_call(
        self,
        messages: list[dict],
        system: dict | None,
        config: dict,
    ) -> tuple[str | None, LLMTokens, Exception | None]:
        output = None
        tokens = LLMTokens()
        exception = None

        try:
            if system:
                api_response = self._client.converse(
                    modelId=self.model.id,
                    messages=messages,
                    system=system,
                    inferenceConfig=config,
                )
            else:
                api_response = self._client.converse(
                    modelId=self.model.id,
                    messages=messages,
                    inferenceConfig=config,
                )

            output = api_response["output"]["message"]["content"][0]["text"]
            tokens = LLMTokens(
                input_tokens=api_response["usage"]["inputTokens"],
                completion_tokens=api_response["usage"]["outputTokens"],
            )

        except Exception as e:
            if hasattr(e, "response"):
                status_code = e.response["ResponseMetadata"]["HTTPStatusCode"]
                error_msg = str(e)

                if status_code == 400:
                    raise ServiceCallException(f"ValidationException: The input fails to satisfy Bedrock constraints: {error_msg}")
                elif status_code == 403:
                    raise ServiceCallException(f"AccessDeniedException: Insufficient permissions to perform this action: {error_msg}")
                elif status_code == 404:
                    raise ServiceCallException(f"ResourceNotFoundException: The specified model was not found: {error_msg}")
                elif status_code == 408:
                    raise ServiceCallException(f"ModelTimeoutException: The request took too long to process: {error_msg}")
                elif status_code == 424:
                    raise ServiceCallException(f"ModelErrorException: The request failed due to a model processing error: {error_msg}")
                elif status_code == 429:
                    # Get retry state from the function wrapper
                    statistics = getattr(self._service_call, "statistics", None)
                    if statistics and statistics["attempt_number"] >= 5:
                        raise ServiceCallThrottlingException(
                            f"ThrottlingException: Request denied due to exceeding account quotas after "
                            f"{statistics['attempt_number']} attempts over {statistics['delay_since_first_attempt']:.1f} seconds"
                        )
                    raise  # Let tenacity retry
                elif status_code == 500:
                    raise ServiceCallException(f"InternalServerException: An internal server error occurred: {error_msg}")
                elif status_code == 503:
                    raise ServiceCallException(f"ServiceUnavailableException: The service is currently unavailable: {error_msg}")

            raise ServiceCallException(f"Unexpected AWS service error: {str(e)}")

        return output, tokens, exception


if __name__ == "__main__":
    from llm_serv.api import get_llm_service
    from llm_serv.registry import REGISTRY

    model = REGISTRY.get_model(provider="AWS", name="claude-3-haiku")
    llm = get_llm_service(model)

    class MyClass(StructuredResponse):
        example_string: str = Field(
            default="", description="A string field that should be filled with a random person name in Elven language"
        )
        example_int: int = Field(
            default=0, ge=0, le=10, description="An integer field with a random value, greater than 5."
        )
        example_float: float = Field(
            default=0, ge=0.0, le=10.0, description="A float field with a value exactly half of the integer value"
        )

    my_class = MyClass()

    conversation = Conversation.from_prompt("Please fill in the following class respecting the following instructions.")
    conversation.add_text_message(role=Role.USER, content=MyClass.to_text())

    request = LLMRequest(conversation=conversation, response_class=MyClass, response_format=LLMResponseFormat.XML)

    response = llm(request)

    print(response)

    assert isinstance(response.output, MyClass)
