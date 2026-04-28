import os
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure we can import from rag_pipeline
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from rag_pipeline.inference.generator import (
    prepare_search_candidates,
    prepare_discovery_candidates,
    run_discovery_page_stream,
    chat_response_stream,
    general_chat_stream,
)
from rag_pipeline.inference.retriever import SchemeResult

app = FastAPI(title="GScheme API", version="1.0")

# Allow the Vite/Next.js frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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

class SchemeResponse(BaseModel):
    id: str
    name: str
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
        description=desc,
        state=s.location_name or "All India",
        category=s.category_name or "General",
        matchScore=score
    )

def stream_generator(generator):
    """Converts Langchain Stream into standard SSE/text chunks."""
    for chunk in generator:
        if hasattr(chunk, "content"):
            yield chunk.content
        else:
            yield str(chunk)

# --- ENDPOINTS ---

@app.post("/api/search", response_model=List[SchemeResponse])
def search_api(req: SearchRequest):
    candidates = prepare_search_candidates(req.query)
    return [map_scheme(c) for c in candidates]

@app.post("/api/discover", response_model=Dict[str, Any])
def discover_api(req: ProfileRequest):
    candidates, is_relaxed = prepare_discovery_candidates(req.profile)
    schemes = [map_scheme(c) for c in candidates]
    
    # We return the list of schemes and a flag.
    # The frontend will make a separate call to stream the summary if needed.
    return {
        "schemes": schemes,
        "is_relaxed": is_relaxed
    }

@app.post("/api/discover-summary")
def discover_summary_api(req: ProfileRequest):
    candidates, is_relaxed = prepare_discovery_candidates(req.profile)
    top_schemes = candidates[:5]
    
    generator = run_discovery_page_stream(
        profile=req.profile,
        top_schemes=top_schemes,
        is_relaxed=is_relaxed
    )
    
    return StreamingResponse(stream_generator(generator), media_type="text/plain")

@app.post("/api/chat")
def chat_api(req: ChatRequest):
    generator = chat_response_stream(
        user_message=req.message,
        profile=req.profile or {},
        scheme_id=req.scheme_id,
        history=req.history
    )
    
    return StreamingResponse(stream_generator(generator), media_type="text/plain")

@app.post("/api/general-chat")
def general_chat_api(req: GeneralChatRequest):
    # Convert dicts back to SchemeResult mock objects for the generator
    class MockSchemeResult:
        def __init__(self, s_dict):
            self.scheme_id = s_dict.get("id")
            
    mock_schemes = [MockSchemeResult(s) for s in req.schemes]
    
    generator = general_chat_stream(
        user_message=req.message,
        profile=req.profile,
        schemes=mock_schemes,
        history=req.history
    )
    
    return StreamingResponse(stream_generator(generator), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8501, reload=True)
