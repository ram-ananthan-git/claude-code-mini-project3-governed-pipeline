from fastapi import FastAPI

from src.router import router

# REQ-SHORT-011: application entry point
app = FastAPI(
    title="URL Shortener Service",
    version="2.0.0",
    description=(
        "Spec-driven URL shortener — SVC-URL-SHORTENER v1.0.0. "
        "Supports creation, redirect, analytics, expiry, and rate limiting."
    ),
)

app.include_router(router)
