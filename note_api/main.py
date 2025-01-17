from uuid import uuid4
from typing import List, Optional
from os import getenv
import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.responses import RedirectResponse
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from pythonjsonlogger import jsonlogger

from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend  # Custom backends
from .model import Note, CreateNoteRequest  # Data model definitions

app = FastAPI()

resource = Resource.create({"service.name": "note-api"})
trace_provider = TracerProvider(resource=resource)
trace_exporter = OTLPSpanExporter(endpoint=getenv("OTLP_ENDPOINT", "https://trace.googleapis.com"))
trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
trace.set_tracer_provider(trace_provider)

FastAPIInstrumentor.instrument_app(app)
LoggingInstrumentor().instrument()

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(message)s %(otelTraceID)s %(otelSpanID)s %(otelTraceSampled)s",
    rename_fields={
        "levelname": "severity",
        "asctime": "timestamp",
        "otelTraceID": "logging.googleapis.com/trace",
        "otelSpanID": "logging.googleapis.com/spanId",
        "otelTraceSampled": "logging.googleapis.com/trace_sampled",
    },
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logHandler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[logHandler])
logger = logging.getLogger("note-api")

my_backend: Optional[Backend] = None

def get_backend() -> Backend:
    global my_backend
    if my_backend is None:
        backend_type = getenv("BACKEND", "memory")
        logger.info(f"Using backend: {backend_type}")
        if backend_type == "redis":
            my_backend = RedisBackend()
        elif backend_type == "gcs":
            my_backend = GCSBackend()
        else:
            my_backend = MemoryBackend()
    return my_backend

@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    return response

@app.get("/")
def redirect_to_notes() -> RedirectResponse:
    return RedirectResponse(url="/notes")

@app.get("/notes")
def get_notes(backend: Backend = Depends(get_backend)) -> List[Note]:
    with trace.get_tracer(__name__).start_as_current_span("get_notes") as span:
        try:
            keys = backend.keys()
            notes = [backend.get(key) for key in keys]
            span.set_attribute("notes.count", len(notes))
            span.add_event("Fetched all notes", {"count": len(notes)})
            return notes
        except Exception as e:
            logger.error("Error fetching notes", exc_info=True)
            span.record_exception(e)
            raise HTTPException(status_code=500, detail="Error fetching notes")

@app.get("/notes/{note_id}")
def get_note(note_id: str, backend: Backend = Depends(get_backend)) -> Note:
    with trace.get_tracer(__name__).start_as_current_span("get_note") as span:
        try:
            span.set_attribute("note.id", note_id)
            span.add_event("Fetching note", {"note.id": note_id})
            note = backend.get(note_id)
            if not note:
                raise HTTPException(status_code=404, detail="Note not found")
            return note
        except Exception as e:
            logger.error(f"Error fetching note with ID {note_id}", exc_info=True)
            span.record_exception(e)
            raise

@app.put("/notes/{note_id}")
def update_note(note_id: str, request: CreateNoteRequest, backend: Backend = Depends(get_backend)) -> None:
    with trace.get_tracer(__name__).start_as_current_span("update_note") as span:
        try:
            span.set_attribute("note.id", note_id)
            backend.set(note_id, request)
            span.add_event("Updated note", {"note.id": note_id})
        except Exception as e:
            logger.error(f"Error updating note with ID {note_id}", exc_info=True)
            span.record_exception(e)
            raise HTTPException(status_code=500, detail="Error updating note")

@app.post("/notes")
def create_note(request: CreateNoteRequest, backend: Backend = Depends(get_backend)) -> str:
    with trace.get_tracer(__name__).start_as_current_span("create_note_span") as span:
        try:
            note_id = str(uuid4())
            backend.set(note_id, request)
            span.set_attribute("note.id", note_id)
            span.add_event("Note created", {"note.id": note_id})
            logger.info("Note created", extra={"note_id": note_id})
            return note_id
        except Exception as e:
            logger.error("Error creating note", exc_info=True)
            span.record_exception(e)
            raise HTTPException(status_code=500, detail="Error creating note")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
