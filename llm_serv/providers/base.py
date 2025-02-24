import abc
import time
from copy import deepcopy
from enum import Enum
from typing import Annotated, Type

from pydantic import BaseModel, Field, PlainSerializer, computed_field, field_validator

from llm_serv.conversation.conversation import Conversation
from llm_serv.exceptions import (
    InternalConversionException,
    ServiceCallException,
    StructuredResponseException,
    ServiceCallThrottlingException,
)
from llm_serv.registry import Model
from llm_serv.structured_response.model import StructuredResponse

class LLMResponseFormat(Enum):
    TEXT = "TEXT"
    JSON = "JSON"
    XML = "XML"


class LLMTokens(BaseModel):
    input_tokens: int = 0
    completion_tokens: int = 0

    @computed_field
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.completion_tokens

    @field_validator("input_tokens", "completion_tokens")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Token counts must be non-negative")
        return v

    def __add__(self, other: "LLMTokens") -> "LLMTokens":
        return LLMTokens(
            input_tokens=self.input_tokens + other.input_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

    def __iadd__(self, other: "LLMTokens") -> "LLMTokens":
        self.input_tokens += other.input_tokens
        self.completion_tokens += other.completion_tokens
        return self


class LLMRequest(BaseModel):
    conversation: Conversation
    response_class: Annotated[Type[StructuredResponse | str], PlainSerializer(lambda obj: obj.__name__)] = Field(
        default=str, exclude=True
    )
    response_format: LLMResponseFormat = LLMResponseFormat.TEXT
    max_completion_tokens: int = 4096
    temperature: float = 0.5
    max_retries: int = 3
    top_p: float = 0.95
    
    class Config:
        arbitrary_types_allowed = True

    @classmethod
    @field_validator("prompt", "messages")
    def check_prompt_or_messages(cls, v, info):
        prompt = info.data.get("prompt")
        messages = info.data.get("messages")
        if prompt is None and messages is None:
            raise ValueError("Either 'prompt' or 'messages' must be provided and not None")
        if prompt is not None and messages is not None:
            raise ValueError("Only one of 'prompt' or 'messages' should be provided")
        return v


class LLMResponse(BaseModel):
    conversation: Conversation | None = None
    output: StructuredResponse | str | dict | None = None
    exception: str | None = None  # this is filled only when there is an error like filtered, for logging purposes
    response_class: Annotated[Type[StructuredResponse | str], PlainSerializer(lambda obj: obj.__name__)] = Field(
        default=str, exclude=True
    )
    response_format: LLMResponseFormat = LLMResponseFormat.TEXT
    max_completion_tokens: int = 1024
    temperature: float = 0.2
    top_p: float = 0.95
    tokens: LLMTokens | None = None
    llm_model: Model | None = None
    start_time: float | None = None  # time.time() as fractions of a second
    end_time: float | None = None  # time.time() as fractions of a second
    total_time: float | None = None  # time in seconds (fractions included)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_request(cls, request: LLMRequest) -> "LLMResponse":
        response_fields = LLMResponse.model_fields
        compatible_fields = {k: v for k, v in request.model_dump().items() if k in response_fields}
        compatible_fields["conversation"] = deepcopy(request.conversation)  # Deep copy the conversation
        response = LLMResponse(**compatible_fields)
        return response


class LLMService(abc.ABC):
    def __init__(self, model: Model):
        self.model = model

    @abc.abstractmethod
    def _convert(self, conversation: Conversation) -> list:
        """
        This method converts the Conversation object to the format each provider requires.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def _service_call(self):
        """
        This method calls the underlying provider directly, and handles failure cases like throttling with retries internally
        """
        raise NotImplementedError()

    def __call__(self, request: LLMRequest) -> LLMResponse:
        try:
            response: LLMResponse = LLMResponse.from_request(request)
            response.start_time = time.time()
            response.llm_model = self.model

            """
            Convert the request to the format the provider requires.
            Raises InternalConversionException if the conversion fails.
            """
            messages, system, config = self._convert(request)

            """
            Calls the underlying provider, and handles failure cases like throttling with retries internally.
            Raises ServiceCallException, ServiceCallThrottlingException if the service call fails.
            """
            output, tokens, exception = self._service_call(messages, system, config)

            if output is None:
                assert exception is not None
                raise ServiceCallException(str(exception))

            response.output = output  # assign initial string output            

            """
            If the response format is XML and the response class is not a string, convert the XML to the desired StructuredResponse class.
            Raises StructuredResponseException if the conversion fails.
            """
            if request.response_format == LLMResponseFormat.XML and request.response_class is not str:
                response.output = request.response_class.from_text(output)

            response.tokens = tokens
            response.exception = str(exception) if exception else None
            response.end_time = time.time()
            response.total_time = response.end_time - response.start_time

            return response

        except (InternalConversionException, ServiceCallThrottlingException, StructuredResponseException) as e:
            # Re-raise these specific exceptions as they are
            raise
        except Exception as e:
            # Wrap any other exception as a ServiceCallException
            raise ServiceCallException(f"Unexpected error during service call: {str(e)}") from e
