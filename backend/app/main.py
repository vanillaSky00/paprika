from fastapi import FastAPI
from app.api.routes import router as api_router

app = FastAPI(
    title="Paprika Agent Backend",
    description="The backend for the Paprika AI agent.",
    version="0.1.0",
)

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Paprika Agent Backend is running."}