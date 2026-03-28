import asyncio
import json
import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

ACTION_SET_MAP = {
    "Vote (Standard approval)": "data/actions/vote.json",
    "Sentiment Scale (1-10)":   "data/actions/vote.json",   # fallback until custom set added
    "Feature Adoption Probability": "data/actions/vote.json",
    "ecommerce": "data/actions/ecommerce.json",
    "social":    "data/actions/social.json",
    "vote":      "data/actions/vote.json",
}

@app.get("/api/simulate")
async def simulate(
    campaign: str = "Should we add a dark mode?",
    agents: int = 5,
    hours: int = 24,
    action_set: str = "Vote (Standard approval)"
):
    actions_path = ACTION_SET_MAP.get(action_set, "data/actions/vote.json")

    async def event_generator():
        cmd = [
            "python3", "-u", "main.py",
            "--campaign", campaign,
            "--agents", str(agents),
            "--hours", str(hours),
            "--actions", actions_path,
            "--ollama-cloud"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode('utf-8').strip()
            # skip empty lines to reduce noise over SSE
            if not decoded_line:
                continue
            yield f"data: {json.dumps({'text': decoded_line})}\n\n"
            
        await process.wait()
        yield f"data: {json.dumps({'done': True})}\n\n"
        
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Mount React Frontend for Production Deployment
frontend_dist = os.path.join(os.path.dirname(__file__), "frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/")
    async def fallback():
        return {"status": "Backend is running. In dev mode, run the frontend via Vite on port 5173."}
