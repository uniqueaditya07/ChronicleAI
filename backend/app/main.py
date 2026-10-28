from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import init_db
from app.api.cases import router as cases_router
from app.api.evidence import router as evidence_router
from app.api.search import router as search_router
from app.api.entities import router as entities_router
from app.api.analysis import router as analysis_router
from app.api.case_tools import router as case_tools_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables safely on startup (additive create_all)
    init_db()
    yield

app = FastAPI(title="ChronicleAI", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    # Error messages must not echo submitted evidence, malformed Unicode or keys.
    details = [{"loc": [str(part).encode("utf-8", "backslashreplace").decode("utf-8") for part in error["loc"]],
                "msg": error["msg"].encode("utf-8", "backslashreplace").decode("utf-8"),
                "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": details})

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(cases_router)
app.include_router(evidence_router)
app.include_router(search_router)
app.include_router(entities_router)
app.include_router(analysis_router)
app.include_router(case_tools_router)

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "ChronicleAI"
    }
