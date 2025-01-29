Work in progress.

# LLM Service

This is a Python package that provides a simple interface for calling LLM services from different providers. I built this as I need full flexibility over the LLM calls and the ability to use different models, providers and modalities at the same time. Use at your own risk.

Supported providers:
- [x] AWS
- [x] Azure
- [ ] OpenAI (to come)
- [ ] Mistral (to come)
- [ ] Anthropic (to come)

## SETUP

### Credentials 

Check out https://www.baeldung.com/ops/docker-container-pass-aws-credentials for fancy ways to pass credentials to a docker container.
We use an .env file to store the credentials for simplicity.
Depending on the provider(s) you want to use, you'll need to set up the following env variables:

For OPENAI:
- OPENAI_API_KEY
- OPENAI_ORGANIZATION
- OPENAI_PROJECT

For AWS:
- AWS_PROFILE
- AWS_DEFAULT_REGION 
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

For Azure:
- AZURE_OPENAI_API_KEY
- AZURE_OPEN_AI_API_VERSION
- AZURE_OPENAI_DEPLOYMENT_NAME


An .env file looks like this:

```
AWS_PROFILE=your-aws-profile-name
AWS_DEFAULT_REGION=your-aws-region-name
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
```

## How to use:

You can use this service in two ways:

1. Direct API usage in your Python code
2. Client-server setup with FastAPI backend

<details> 
<summary><h3> Python API</h3></summary> 

The direct API allows you to interact with LLM providers without running a server. Here's a basic example:

```python
from llm_serv.providers.base import LLMRequest
from llm_serv.registry import REGISTRY
from llm_serv.api import get_llm_service
from llm_serv.conversation.conversation import Conversation

# List available providers and models
providers = REGISTRY.providers
models = REGISTRY.models

# Select a model and create service
model = REGISTRY.get_model(provider='AWS', name='claude-3-haiku')
llm_service = get_llm_service(model)

# Create conversation and request
conversation = Conversation.from_prompt("What's 1+1?")
request = LLMRequest(conversation=conversation)

# Get response
response = llm_service(request)
print(response.output)
```
For more details, see the complete example in examples/example_api.py.

</details>

<details> 
<summary><h3> Client</h3></summary> 

### Setup server

You can run the server either locally or using Docker.

<details> 
<summary><h4> Setup local instance</h4></summary> 

1. Install the package and its dependencies:

```bash
poetry install
```

2. Run the FastAPI server:
```bash
python -m llm_serv.server
```

3. The server will be available at `http://localhost:10000`.

</details>

<details> 
<summary><h4> Setup docker container</h4></summary> 

1. Build the Docker image:

```bash
docker build -t llm-service .
```

2. Run the container:
```bash
docker run -d \
-p 10000:10000 \
-e AWS_PROFILE=your-aws-profile-name \
-e AWS_DEFAULT_REGION=your-aws-region-name \
-e AWS_ACCESS_KEY_ID=your-aws-access-key-id \
-e AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key \
llm-service
```

3. The server will be available at `http://localhost:10000`.

</details>

### Use the client

Here's a basic example of using the client:

```python
import asyncio
from llm_serv.client import LLMServiceClient
from llm_serv.conversation.conversation import Conversation
from llm_serv.providers.base import LLMRequest

async def main():
    # Initialize the client
    client = LLMServiceClient(host="localhost", port=10000)

    # List available providers and models
    providers = await client.list_providers()
    all_models = await client.list_models()

    # Set the model to use
    client.set_model(provider="AWS", name="claude-3-haiku")

    # Create and send a chat request
    conversation = Conversation.from_prompt("What's 1+1?")

    request = LLMRequest(conversation=conversation)

    response = await client.chat(request)
    
    print("Response:", response)

if __name__ == "__main__":
    asyncio.run(main())
```

For more details, see the complete example in ``examples/example_client.py``.

</details>


## TODOs

- [x] Add OpenAI support
- [ ] Add Anthropic support
- [ ] Add streaming support
- [ ] Add caching support
- [ ] Add local LLM support 
- [ ] Restore image capabilities
- [ ] Restore document capabilities
- [X] Add XML lazy structured output support
    - [ ] Handle | operator, not only Optional[]
    - [ ] Full testing for this
- [ ] Add provider-specific structured output support
- [ ] Add proper logging
- [ ] Add tests
- [ ] Add proper documentation
- [ ] Add better healthcheck with uptime and token count
- [ ] Add better credentials check at initialization
