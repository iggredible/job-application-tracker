from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.ai.types import AIConfigurationError
from app.api import analysis, applications, coverage, health, resume
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware

configure_logging()

app = FastAPI(title="Job Application Tracker")
app.add_middleware(RequestLoggingMiddleware)
app.include_router(health.router)
app.include_router(applications.router)
app.include_router(resume.router)
app.include_router(analysis.router)
app.include_router(coverage.router)


@app.exception_handler(AIConfigurationError)
def ai_not_configured(request: Request, exc: AIConfigurationError) -> JSONResponse:
    """The key or model is missing, so no call was made. The message names an environment
    variable, which is for the person running the server, not for the browser."""
    return JSONResponse(status_code=503, content={"detail": "AI is not configured."})
