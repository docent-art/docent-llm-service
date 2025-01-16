import os
from openai import AzureOpenAI
from pydantic import Field
from tenacity import retry, stop_after_attempt, wait_exponential

from llm_serv.conversation.message import Message
from llm_serv.conversation.role import Role
from llm_serv.providers.base import LLMService, LLMRequest, LLMTokens, LLMResponseFormat
from llm_serv.conversation.conversation import Conversation
from llm_serv.registry import Model
from llm_serv.structured_response.model import StructuredResponse
from llm_serv.conversation.image import Image


def check_credentials() -> None:
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPEN_AI_API_VERSION = os.getenv("AZURE_OPEN_AI_API_VERSION")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    
    if not AZURE_OPENAI_API_KEY or not AZURE_OPEN_AI_API_VERSION or not AZURE_OPENAI_DEPLOYMENT_NAME:
        raise Exception("Environment variable AZURE_OPENAI_API_KEY and/or AZURE_OPEN_AI_API_VERSION and/or AZURE_OPENAI_DEPLOYMENT_NAME are not set!")


class AzureOpenAILLMService(LLMService):
    def __init__(self, model: Model):
        self.model=model

        self._client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPEN_AI_API_VERSION"),
            azure_endpoint=f"https://{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}.openai.azure.com",
        )

    def _convert(self, request:LLMRequest) -> tuple[list, dict, dict]:
        """
        Ref here: https://platform.openai.com/docs/api-reference/chat/object
        https://platform.openai.com/docs/guides/vision#multiple-image-inputs
        returns (messages, system, config)

        Example how to send multiple images as urls:
        client = OpenAI()
        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
        {
            "role": "user",
            "content": [
            {
                "type": "text",
                "text": "What are in these images? Is there any difference between them?",
            },
            {
                "type": "image_url",
                "image_url": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                },
            },
            {
                "type": "image_url",
                "image_url": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                },
            },
            ],
        }
        ],
        max_tokens=300,
        )

        and example how to send an image as base64:

        import base64
        from openai import OpenAI

        client = OpenAI()

        # Function to encode the image
        def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

        # Path to your image
        image_path = "path_to_your_image.jpg"

        # Getting the base64 string
        base64_image = encode_image(image_path)

        response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": "What is in this image?",
                },
                {
                "type": "image_url",
                "image_url": {
                    "url":  f"data:image/jpeg;base64,{base64_image}"
                },
                },
            ],
            }
        ],
        )
        """
        messages = []
        
        # Handle system message if present
        if request.conversation.system is not None and len(request.conversation.system) > 0:
            messages.append({
                "role": Role.SYSTEM.value, 
                "content": [{"type": "text", "text": request.conversation.system}]
            })

        # Process each message
        for message in request.conversation.messages:
            content = []
            
            # Add text content if present
            if message.text:
                content.append({
                    "type": "text",
                    "text": message.text
                })
            
            # Add images if present
            for image in message.images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{image.format or 'jpeg'};base64,{image.export_as_base64(image.image)}",
                        "detail": "high"
                    }
                })
            
            messages.append({
                "role": message.role.value,
                "content": content
            })

        config = {
            "max_tokens": request.max_completion_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "response_format": {"type": "json_object"} if request.response_format == LLMResponseFormat.JSON else {"type": "text"}
        }

        return messages, None, config

    @retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=3, max=60))
    def _service_call(self, 
                      messages: list[dict],  
                      system:dict | None,
                      config:dict,
                      ) -> tuple[str | None, LLMTokens, Exception | None]:
        output = None
        tokens = LLMTokens()
        exception = None

        try:
            api_response =  self._client.chat.completions.create(
                model=self.model.id,
                messages=messages,
                max_tokens=config['max_tokens'],
                temperature=config['temperature'],
                top_p=config['top_p'],
                response_format=config['response_format']
            )
            output = api_response.choices[0].message.content
            tokens = LLMTokens(
                input_tokens=api_response.usage.prompt_tokens,
                completion_tokens=api_response.usage.completion_tokens,
                total_tokens=api_response.usage.total_tokens
            )
            
        except Exception as exception:
            print(str(exception))
            if hasattr(exception, 'status_code'):
                if exception.status_code == 400:
                    return output, tokens, exception
                elif exception.status_code == 429:  # Retry with exponential backoff
                    statistics = getattr(self._service_call, 'statistics', None)
                    if statistics:                        
                        print(f"Call throttling, attempt number {statistics['attempt_number']}, idle for {statistics['idle_for']:.1f} seconds, delay since first attempt {statistics['delay_since_first_attempt']:.1f} seconds.")
                    raise exception
            raise exception
        
        return output, tokens, exception

if __name__ == "__main__":
    from llm_serv.api import get_llm_service
    from llm_serv.registry import REGISTRY    

    model = REGISTRY.get_model(provider='AZURE', name='gpt-4o-mini')
    llm = get_llm_service(model)
    
    class MyClass(StructuredResponse):
        example_string: str = Field(default="", description="A string field that should be filled with a random person name in Elven language")
        example_int: int = Field(default=0, ge=0, le=10, description="An integer field with a random value, greater than 5.")
        example_float: float = Field(default=0, ge=0.0, le=10.0, description="A float field with a value exactly half of the integer value")
        
    my_class = MyClass()

    conversation = Conversation.from_prompt("Please fill in the following class respecting the following instructions.")
    conversation.add_text_message(role=Role.USER, content=MyClass.to_xml())

    request = LLMRequest(
        conversation=conversation,
        response_class=MyClass,
        response_format=LLMResponseFormat.XML
        )

    response = llm(request)

    print(response)

    assert isinstance(response.output, MyClass)
