from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import uvicorn


from .core.config import settings
from .packages import get_logger
from .api.v1 import api_router

logger = get_logger(__name__)


# lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    
    if settings.chat_agent_api_key is None:
        logger.error("CHAT_AGENT_API_KEY is not set. Please set it in the environment variables.")
        raise HTTPException(status_code=500, detail="CHAT_AGENT_API_KEY is not set.")
    
    logger.info("All required API keys are set. Starting the application...")

    
    yield

    logger.info("Shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title= settings.PROJECT_NAME,
        description= settings.DESCRIPTION,
        version= settings.VERSION,
        lifespan=lifespan
    )
    
    # Include routers
    app.include_router(api_router, tags=["API"])
    
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}
    
    return app

app = create_app()

def main():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,
    )

if __name__ == "__main__":
    main()