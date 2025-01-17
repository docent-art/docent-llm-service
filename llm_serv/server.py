import logging
import os

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from llm_serv.api import get_llm_service
from llm_serv.providers.base import LLMRequest, LLMResponse
from llm_serv.registry import REGISTRY, Model

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Initialize the registry first
        logger.info("Initializing LLM Registry...")
        _ = REGISTRY.models
        logger.info(f"Registry initialized with {len(REGISTRY.models)} models")
    except Exception as e:
        logger.error(f"Failed to initialize registry: {str(e)}")
        raise

    app = FastAPI(
        title="LLMService", 
        version="1.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add error handlers
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app

app = create_app()

@app.get("/list_models")
async def list_models() -> list[Model]:
    print("Listing models...")
    print(REGISTRY.models)
    try:
        return REGISTRY.models
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list_providers")
async def list_providers() -> list[str]:
    print("Listing providers...")
    try:
        # Extract unique provider names from the models
        providers = list({model.provider.name for model in REGISTRY.models})
        return providers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/{model_provider}/{model_name}")
async def chat(
    model_provider: str,
    model_name: str,
    request: LLMRequest
) -> LLMResponse:
    print(f"\n Chatting with model {model_provider}/{model_name}")
    print(request)
    model = REGISTRY.get_model(provider=model_provider, name=model_name)
    llm_service = get_llm_service(model)
    return llm_service(request)

@app.get("/health")
async def health_check():
    try:
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

def main():    
    port = int(os.getenv("API_PORT", "10000"))
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()