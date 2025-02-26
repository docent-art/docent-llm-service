"""
    This example demonstrates how to use the LLM Service direct API to interact with models.
    Unlike the client example that requires a running server, this approach allows direct 
    interaction with the LLM providers.

"""

from rich import print as rprint

from llm_serv.api import get_llm_service
from llm_serv.conversation.conversation import Conversation
from llm_serv.conversation.role import Role
from llm_serv.providers.base import LLMRequest
from llm_serv.registry import REGISTRY

# Select a model and create service
model = REGISTRY.get_model(provider="OPENAI", name="gpt-4o-mini")
llm_service = get_llm_service(model)

# Create conversation and request
conversation = Conversation(system="Let's play a game. I say a number, then you add 1 to it. Respond only with the number.")
conversation.add_text_message(role=Role.USER, content="I start, 3.")

# Run request and get a response
response = llm_service(LLMRequest(conversation=conversation))

# Add the response to the conversation
conversation.add_text_message(role=Role.ASSISTANT, content=response.output)

# New user message
conversation.add_text_message(role=Role.USER, content="8")

# Run request and get a response
response = llm_service(LLMRequest(conversation=conversation))

# Add the new response to the conversation
conversation.add_text_message(role=Role.ASSISTANT, content=response.output)

response.rprint()

