import os
import sys
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure we can import from rag_pipeline
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_project_root / ".env")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

from rag_pipeline.inference.generator import (
    prepare_search_candidates,
    prepare_discovery_candidates,
    run_discovery_page_stream,
    chat_response_stream,
    general_chat_stream,
)
from rag_pipeline.inference.retriever import SchemeResult
from rag_pipeline.inference.retriever import KnowledgeBaseUnavailableError
from rag_pipeline.inference.compare import (
    get_scheme_comparison_data,
    get_multiple_scheme_comparison,
)

app = FastAPI(title="GScheme API", version="1.0")
logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://g-scheme.vercel.app",
    "http://localhost:5173",
]


def _get_cors_origins() -> List[str]:
    raw_origins = os.environ.get("CORS_ORIGINS") or os.environ.get("FRONTEND_ORIGINS")
    if not raw_origins:
        return DEFAULT_CORS_ORIGINS
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",")]
    return [origin for origin in origins if origin]


# Allow the Next.js frontend to talk to this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- MODELS ---

class SearchRequest(BaseModel):
    query: str

class ProfileRequest(BaseModel):
    profile: Dict[str, Any]

class ChatRequest(BaseModel):
    scheme_id: str
    message: str
    history: List[Dict[str, str]]
    profile: Optional[Dict[str, Any]] = None

class GeneralChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]]
    profile: Dict[str, Any]
    schemes: List[Dict[str, Any]]

class CompareRequest(BaseModel):
    scheme_ids: List[str]

class SchemeResponse(BaseModel):
    id: str
    name: str
    url: str = ""
    description: str
    state: str
    category: str
    matchScore: Optional[int] = None

# --- HELPERS ---

def map_scheme(s: SchemeResult) -> SchemeResponse:
    # SchemeResult doesn't have a small description by default.
    # We'll extract a short snippet from combined_text if available.
    desc = s.combined_text[:150] + "..." if s.combined_text else ""
    
    score = min(100, int(s.score * 100)) if getattr(s, "score", None) else None
    
    return SchemeResponse(
        id=s.scheme_id,
        name=s.scheme_name,
        url=s.scheme_url or "",
        description=desc,
        state=s.location_name or "All India",
        category=s.category_name or "General",
        matchScore=score
    )

def stream_generator(generator):
    """Converts Langchain Stream into standard SSE/text chunks."""
    try:
        for chunk in generator:
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)
    except Exception as exc:
        logger.exception("Streaming response failed")
        if isinstance(exc, KnowledgeBaseUnavailableError):
            yield str(exc)
            return
        yield "\n\nSorry, I hit a backend issue while processing that request."

# --- ENDPOINTS ---

@app.get("/")
def root():
    return {"ok": True, "service": "GScheme API"}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/api/search", response_model=List[SchemeResponse])
def search_api(req: SearchRequest):
    try:
        candidates = prepare_search_candidates(req.query)
    except KnowledgeBaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [map_scheme(c) for c in candidates]

@app.post("/api/discover", response_model=Dict[str, Any])
def discover_api(req: ProfileRequest):
    try:
        candidates, is_relaxed = prepare_discovery_candidates(req.profile)
    except KnowledgeBaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    schemes = [map_scheme(c) for c in candidates]
    
    # We return the list of schemes and a flag.
    # The frontend will make a separate call to stream the summary if needed.
    return {
        "schemes": schemes,
        "is_relaxed": is_relaxed
    }

@app.post("/api/discover-summary")
def discover_summary_api(req: ProfileRequest):
    try:
        candidates, is_relaxed = prepare_discovery_candidates(req.profile)
    except KnowledgeBaseUnavailableError as exc:
        return StreamingResponse(iter([str(exc)]), media_type="text/plain")
    top_schemes = candidates[:5]
    
    generator = run_discovery_page_stream(
        profile=req.profile,
        top_schemes=top_schemes,
        is_relaxed=is_relaxed
    )
    
    return StreamingResponse(stream_generator(generator), media_type="text/plain")

@app.post("/api/chat")
def chat_api(req: ChatRequest):
    try:
        generator = chat_response_stream(
            user_message=req.message,
            profile=req.profile or {},
            scheme_id=req.scheme_id,
            history=req.history
        )
    except KnowledgeBaseUnavailableError as exc:
        return StreamingResponse(iter([str(exc)]), media_type="text/plain")
    
    return StreamingResponse(stream_generator(generator), media_type="text/plain")

@app.post("/api/general-chat")
def general_chat_api(req: GeneralChatRequest):
    # Convert dicts back to SchemeResult mock objects for the generator
    class MockSchemeResult:
        def __init__(self, s_dict):
            self.scheme_id = s_dict.get("id")
            
    mock_schemes = [MockSchemeResult(s) for s in req.schemes]
    
    try:
        generator = general_chat_stream(
            user_message=req.message,
            profile=req.profile,
            schemes=mock_schemes,
            history=req.history
        )
    except KnowledgeBaseUnavailableError as exc:
        return StreamingResponse(iter([str(exc)]), media_type="text/plain")
    
    return StreamingResponse(stream_generator(generator), media_type="text/plain")

# --- COMPARISON ENDPOINTS ---

@app.post("/api/compare")
def compare_api(req: CompareRequest):
    """Return structured comparison data for 2-3 schemes."""
    if len(req.scheme_ids) < 2 or len(req.scheme_ids) > 3:
        raise HTTPException(status_code=400, detail="Provide 2 or 3 scheme IDs")
    try:
        return get_multiple_scheme_comparison(req.scheme_ids)
    except KnowledgeBaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

@app.get("/api/scheme/{scheme_id}/compare-data")
def scheme_compare_data(scheme_id: str):
    """Return structured comparison data for a single scheme."""
    try:
        return get_scheme_comparison_data(scheme_id)
    except KnowledgeBaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

# --- STT ENDPOINT ---

@app.post("/api/stt")
async def speech_to_text(
    file: UploadFile = File(...),
    mode: str = Form("transcribe"),
):
    """
    Proxy audio to Sarvam AI Saaras STT API.
    Returns transcript and detected language.
    """
    sarvam_key = os.environ.get("SARVAM_API_KEY")
    if not sarvam_key:
        raise HTTPException(status_code=500, detail="SARVAM_API_KEY not configured")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty")
    content_type = (file.content_type or "audio/webm").split(";")[0].strip().lower()
    if content_type in {"audio/x-wav", "audio/wave"}:
        content_type = "audio/wav"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": sarvam_key},
                files={"file": (file.filename or "audio.webm", audio_bytes, content_type)},
                data={
                    "model": "saaras:v3",
                    "mode": mode,
                    "language_code": "unknown",
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or "Sarvam API request failed"
        logger.warning("Sarvam STT request failed: %s", detail)
        raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Sarvam STT service") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid response from Sarvam STT service") from exc
    return {
        "transcript": result.get("transcript", ""),
        "language_code": result.get("language_code", "unknown"),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8501, reload=True)
