"""Main module."""

from fastapi import FastAPI

from retail.plugins.square_plugin import router as square_router

app = FastAPI()

app.include_router(square_router, prefix="/square", tags=["Square"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Synvya Retail Commerce API is running!"}
