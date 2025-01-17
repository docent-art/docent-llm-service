import logging
import os
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.middleware.gzip import GZipMiddleware

from llm_serv.api import get_llm_service
from llm_serv.providers.base import LLMRequest, LLMResponse
from llm_serv.registry import REGISTRY, Model

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    try:
        # Initialize the registry first
        logger.info("Initializing LLM Registry...")
        _ = REGISTRY.models
        logger.info(f"Registry initialized with {len(REGISTRY.models)} models")
    except Exception as e:
        logger.error(f"Failed to initialize registry: {str(e)}")
        raise

    app = FastAPI(title="LLMService", version="1.0", docs_url="/docs", redoc_url="/redoc")

    # Store startup time and initialize metrics
    app.state.start_time = time.time()
    app.state.chat_request_count = 0
    app.state.model_usage = {}  # tracks detailed usage per model
    app.state.total_tokens = {"input": 0, "completion": 0, "total": 0}

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add compression middleware - compress responses > 1KB
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,  # 1KB
        content_types=[
            'application/json',
            'text/plain',
        ]
    )

    # Add error handlers
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()


@app.get("/list_models")
async def list_models() -> list[Model]:
    try:
        logger.info("Listing models...")
        models = REGISTRY.models
        logger.info(f"Found {len(models)} models")
        return models
    except Exception as e:
        logger.error(f"Failed to list models: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve model list: {str(e)}") from e


@app.get("/list_providers")
async def list_providers() -> list[str]:
    try:
        logger.info("Listing providers...")
        providers = list({model.provider.name for model in REGISTRY.models})
        logger.info(f"Found {len(providers)} providers: {providers}")
        return providers
    except Exception as e:
        logger.error(f"Failed to list providers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve provider list: {str(e)}") from e


@app.post("/chat/{model_provider}/{model_name}")
async def chat(model_provider: str, model_name: str, request: LLMRequest) -> LLMResponse:
    try:
        logger.info(f"Chatting with model {model_provider}/{model_name}")
        logger.info(f"Request: {request}")

        # Increment chat request counters
        app.state.chat_request_count += 1

        # Update model-specific usage counter with detailed metrics
        model_key = f"{model_provider}.{model_name}"
        if model_key not in app.state.model_usage:
            app.state.model_usage[model_key] = {
                "chat_request_count": 0,
                "tokens": {"input": 0, "completion": 0, "total": 0},
            }

        try:
            model = REGISTRY.get_model(provider=model_provider, name=model_name)
        except KeyError as e:
            logger.error(f"Model not found: {model_provider}/{model_name}")
            raise HTTPException(status_code=404, detail=f"Model {model_provider}/{model_name} not found") from e

        try:
            llm_service = get_llm_service(model)
            response = llm_service(request)
        except Exception as e:
            logger.error(f"LLM service error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing chat request: {str(e)}") from e

        logger.info(f"Response: {response}")

        # Update both global and model-specific token counts
        try:
            app.state.total_tokens["input"] += response.usage.prompt_tokens
            app.state.total_tokens["completion"] += response.usage.completion_tokens
            app.state.total_tokens["total"] += response.usage.total_tokens

            # Update model-specific metrics
            app.state.model_usage[model_key]["chat_request_count"] += 1
            app.state.model_usage[model_key]["tokens"]["input"] += response.usage.prompt_tokens
            app.state.model_usage[model_key]["tokens"]["completion"] += response.usage.completion_tokens
            app.state.model_usage[model_key]["tokens"]["total"] += response.usage.total_tokens
        except Exception as e:
            logger.error(f"Error updating metrics: {str(e)}", exc_info=True)
            # Don't raise here - metrics errors shouldn't affect the response

        return response

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred processing your request") from e


@app.get("/health")
async def health_check(request: Request):
    try:
        uptime_seconds = time.time() - request.app.state.start_time

        # Calculate days, hours, minutes, seconds
        days, remainder = divmod(int(uptime_seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        # Format uptime string
        uptime_parts = []
        if days > 0:
            uptime_parts.append(f"{days}d")
        if hours > 0:
            uptime_parts.append(f"{hours}h")
        if minutes > 0:
            uptime_parts.append(f"{minutes}m")
        uptime_parts.append(f"{seconds}s")

        health_data = {
            "status": "healthy",
            "uptime": " ".join(uptime_parts),
            "chat_requests": request.app.state.chat_request_count,
            "model_usage": request.app.state.model_usage,
            "tokens": request.app.state.total_tokens,
        }
        logger.debug(f"Health check response: {health_data}")
        return health_data
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service health check failed: {str(e)}") from e


def main():
    try:
        port = int(os.getenv("API_PORT", "10000"))
        logger.info(f"Starting server on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    except ValueError as e:
        logger.error(f"Invalid port configuration: {str(e)}", exc_info=True)
        raise SystemExit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}", exc_info=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
