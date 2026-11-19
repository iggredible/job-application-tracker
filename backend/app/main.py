from fastapi import FastAPI

from app.api import applications, health, resume
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware

configure_logging()

app = FastAPI(title="Job Application Tracker")
app.add_middleware(RequestLoggingMiddleware)
app.include_router(health.router)
app.include_router(applications.router)
app.include_router(resume.router)
