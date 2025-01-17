"""
    This example demonstrates how to use the LLM Service API to interact with a model.
    It uses the LLMServiceClient to interact with the API and the LLMRequest to send a request to the API.
    It requires a server instance to be running.

    You can run the backend FastAPI server by running the python command from the root of the repository:

    ```bash
    python -m llm_serv.server
    ``` 

    Ensure you have the proper credential set up, depending on the provider(s) you are using.

    
    Alternatively, you can run the server in a docker container.   
    
    First, build the docker image by running the following command:

    ```bash
    docker build -t llm-service .
    ```

    Then you can run the API by running the following command:

    ```bash
    docker run -d \
        -p 10000:10000 \
        -e AWS_PROFILE=your-aws-profile-name \
        -e AWS_DEFAULT_REGION=your-aws-region-name \
        -e AWS_ACCESS_KEY_ID=your-aws-access-key-id \
        -e AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key \
        llm-service
    ```

    This will start the API and the API will be available at http://localhost:10000.
"""

import asyncio
from llm_serv.client import LLMServiceClient
from llm_serv.conversation.conversation import Conversation
from llm_serv.providers.base import LLMRequest
from rich import print as rprint

async def main():
    # 1. Initialize the client
    client = LLMServiceClient(host="localhost", port=10000)

    # 2. List available providers
    # Returns a list of provider names like ["AWS", "AZURE", "OPENAI"]
    providers = await client.list_providers()
    print("Available providers:", providers)

    # 3. List available models
    # Returns all models across all providers
    all_models = await client.list_models()
    print("All available models:", all_models)

    # List models for a specific provider
    aws_models = await client.list_models(provider="AWS")
    print("AWS models:", aws_models)

    # 4. Set the model to use
    client.set_model(provider="AWS", name="claude-3-haiku")

    # 5. Create and send a chat request
    conversation = Conversation.from_prompt("What's 1+1?")
    request = LLMRequest(conversation=conversation)
    response = await client.chat(request)

    rprint("Full Response:", response)

    rprint("Output:", response.output)

    rprint("Token Usage:", response.tokens)


if __name__ == "__main__":
    asyncio.run(main())
