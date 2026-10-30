from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
import uvicorn

app = FastAPI(title="Agricultural Intrusion Detection API - Pi Edge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {
        "message": "Agricultural Intrusion Detection System API (Pi Edge Edition)",
        "version": "2.0.0",
        "endpoints": {
            "events": "/api/events",
            "intrusions": "/api/intrusions",
            "recognized": "/api/recognized",
            "stats": "/api/stats",
            "detect": "/api/detect",             # New Pi upload endpoint
            "pi_capture": "/api/pi/capture",     # New manual trigger endpoint
            "pi_stream": "/api/pi/stream"        # New SSE stream for Pi
        }
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)