import os
import re
import sys
import json
import queue
import asyncio
import tempfile
import threading
import contextlib

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ------------------------------------------------------------------ الإعدادات
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "30"))
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
RATE_PER_MIN = os.environ.get("RATE_PER_MIN", "5/minute")
RATE_PER_DAY = os.environ.get("RATE_PER_DAY", "80/day")
MAX_INFLIGHT = int(os.environ.get("MAX_INFLIGHT", "4"))
MODELS = None
_convert_lock = threading.Lock()
_inflight_lock = threading.Lock()
_inflight = 0

limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_PER_DAY])


class QueueWriter:
    _BAR = re.compile(r"[|█▏▎▍▌▋▊▉▐░▒▓#=\-]{2,}")
    _PCT = re.compile(r"(\d{1,3})\s*%")

    def __init__(self, q: "queue.Queue"):
        self.q = q
        self.buf = ""

    def write(self, text):
        if not text:
            return
        self.buf += text
        parts = re.split(r"[\r\n]", self.buf)
        self.buf = parts.pop()
        for line in parts:
            self._emit(line)

    def _emit(self, line):
        line = line.strip()
        if not line:
            return
        m = self._PCT.search(line)
        if m:
            try:
                self.q.put({"progress": max(0, min(100, int(m.group(1))))})
            except Exception:
                pass
        clean = self._BAR.sub(" ", line).strip()
        clean = re.sub(r"\s{2,}", " ", clean)
        if clean:
            self.q.put({"log": clean})

    def flush(self):
        pass

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global MODELS
    from marker.models import create_model_dict
    print("[backend] loading AI models (first run may download them)…")
    MODELS = create_model_dict()
    print("[backend] models ready.")
    yield
    MODELS = None


app = FastAPI(title="Research Markdown API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "models_loaded": MODELS is not None}


@app.post("/convert")
@limiter.limit(RATE_PER_MIN)
async def convert(request: Request, file: UploadFile = File(...)):
    global _inflight

    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF files only")

    data = await file.read()
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_MB} MB")
    if not data[:5].startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="Not a valid PDF file")
    if MODELS is None:
        raise HTTPException(status_code=503, detail="Models still loading, try again shortly")

    with _inflight_lock:
        if _inflight >= MAX_INFLIGHT:
            raise HTTPException(status_code=503, detail="Server busy, please try again shortly")
        _inflight += 1

    q: "queue.Queue" = queue.Queue()

    def worker():
        global _inflight
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(data)
        tmp.close()
        old_out, old_err = sys.stdout, sys.stderr
        with _convert_lock:
            writer = QueueWriter(q)
            try:
                sys.stdout = writer
                sys.stderr = writer
                q.put({"stage": "acc_stage1"})
                q.put({"log": "initializing precise converter"})

                from marker.converters.pdf import PdfConverter

                converter = PdfConverter(artifact_dict=MODELS)
                q.put({"log": "running layout, equation & table models"})
                rendered = converter(tmp.name)

                md = getattr(rendered, "markdown", None)
                if md is None:
                    from marker.output import text_from_rendered
                    md, _, _ = text_from_rendered(rendered)

                q.put({"progress": 100})
                q.put({"log": "done"})
                q.put({"markdown": md})
            except Exception as e:  # noqa: BLE001
                sys.stdout, sys.stderr = old_out, old_err
                q.put({"error": str(e)})
            finally:
                sys.stdout, sys.stderr = old_out, old_err
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
                with _inflight_lock:
                    _inflight -= 1
                q.put(None) 

    threading.Thread(target=worker, daemon=True).start()

    async def stream():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            if item is None:
                break
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
