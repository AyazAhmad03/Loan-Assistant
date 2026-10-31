
from fastapi import FastAPI
from app.api.routes import health

# Initialize FastAPI application
app = FastAPI(
    title="Loan Assistant API",
    description="AI-powered Loan Intelligence Assistant",
    version="1.0.0"
)

# Register API routes
app.include_router(health.router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to Loan Assistant API",
        "status": "running",
        "version": "1.0.0"
    }
