from enum import Enum
from typing import Optional

from pydantic import Field
from llm_serv.providers.base import LLMRequest, LLMResponseFormat
from llm_serv.registry import REGISTRY
from llm_serv.api import get_llm_service
from llm_serv.conversation.conversation import Conversation
from rich import print as rprint
from llm_serv.client import LLMServiceClient

from llm_serv.structured_response.model import StructuredResponse

model = REGISTRY.get_model(provider='AWS', name='claude-3-haiku')
llm_service = get_llm_service(model)

input_text = """
The temperature today in Annecy is 10°C. There is a 80% chance of rain in the morning and 20% chance of rain in the afternoon. Winds will be from the south at 5 km/h.
We expect a high of 15°C and a low of 5°C.
"""

class ChanceScale(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class RainProbability(StructuredResponse):
    chance: ChanceScale = Field(description="The chance of rain, where low is less than 25% and high is more than 75%")
    when: str = Field(description="The time of day when the rain is or is not expected")

class WeatherPrognosis(StructuredResponse):
    location: str = Field(description="The location of the weather forecast")
    current_temperature: float = Field(description="The current temperature in degrees Celsius")
    rain_probability: Optional[list[RainProbability]] = Field(description="The chance of rain, where low is less than 25% and high is more than 75%")
    wind_speed: Optional[float] = Field(description="The wind speed in km/h")
    high: Optional[float] = Field(ge=-20, le=60, description="The high temperature in degrees Celsius")
    low: Optional[float] = Field(description="The low temperature in degrees Celsius")


async def main():
    # Initialize the client
    client = LLMServiceClient(host="localhost", port=10000)
    
    # Set the model to use
    client.set_model(provider="AWS", name="claude-3-haiku")

    prompt = f"""
    You are a weather expert. You are given a weather forecast for a specific location.

    Here is the weather forecast:
    {input_text}

    Here is the structured response:
    {WeatherPrognosis.to_text()}
    """

    print(prompt)

    conversation = Conversation.from_prompt(prompt)
    request = LLMRequest(conversation=conversation,
                        response_class=WeatherPrognosis,
                        response_format=LLMResponseFormat.XML,
                        max_completion_tokens=4000,
                        )

    response = await client.chat(request)

    print("\nResponse:")
    rprint(response.output)

    print(f"Output type: {type(response.output)}")
    assert isinstance(response.output, WeatherPrognosis)

    rprint("Token Usage:", response.tokens)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

