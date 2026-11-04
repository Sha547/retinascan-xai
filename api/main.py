"""RetinaScan XAI API. docs/CONTRACT.md is the source of truth for every response.

Run from the repo root:
    uvicorn api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import io
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.inference import ModelUnavailable, Predictor, load_predictor, priority_for, recommendation_for
from api.store import CaseNotFound, DecisionNotAllowed, Store, now_iso
from ml import quality

CONTRACT_VERSION = 1
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
# Multipart boundaries and form fields add a little to the request size.
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
# A small PNG can decode to gigabytes, so dimensions are checked before decoding.
MAX_IMAGE_PIXELS = 60_000_000
MAX_PATIENT_ID_LENGTH = 64
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
IMAGE_TYPES = {"JPEG": ".jpg", "PNG": ".png"}
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png"}
DISCLAIMER = (
    "Research prototype, not clinically validated. "
    "Final decision must be made by a qualified ophthalmologist."
)
ERROR_CODES = {
    400: "bad_request",
    404: "not_found",
    405: "bad_request",
    409: "bad_request",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    503: "model_unavailable",
}

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
logger = logging.getLogger("retinascan.api")


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        self.status = status
        self.message = message
        self.code = code or ERROR_CODES[status]


class DecisionIn(BaseModel):
    action: Literal["accept", "override"]
    reviewer: str
    note: str = ""
    final_grade: Any = None  # only read for override, so accept can ignore bad values

    @field_validator("reviewer")
    @classmethod
    def reviewer_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reviewer must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def override_needs_grade(self):
        if self.action == "override":
            grade = self.final_grade
            if type(grade) is not int or not 0 <= grade <= 4:
                raise ValueError("final_grade must be an integer from 0 to 4 for override")
        return self


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def load_quality_thresholds() -> dict:
    derived = ARTIFACTS / "quality_thresholds.json"
    if derived.is_file():
        return quality.load_thresholds(derived)
    logger.warning("Using PLACEHOLDER quality thresholds: %s not found", derived)
    placeholder = Path(quality.__file__).with_name("quality_thresholds.placeholder.json")
    return quality.load_thresholds(placeholder, allow_placeholder=True)


def read_upload(upload: UploadFile) -> tuple[bytes, str]:
    """Return (bytes, suffix). The type comes from the content, not the client's header."""
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(413, "Image is larger than the 15 MB limit.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError):
        raise ApiError(415, "Upload a JPEG or PNG image.") from None
    except Image.DecompressionBombError:
        raise ApiError(400, "Image dimensions are too large.") from None
    if image_format not in IMAGE_TYPES:
        raise ApiError(415, "Upload a JPEG or PNG image.")
    if width * height > MAX_IMAGE_PIXELS:
        raise ApiError(400, "Image dimensions are too large.")
    return data, IMAGE_TYPES[image_format]


def decode_bgr(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ApiError(415, "Upload a JPEG or PNG image.")
    return image


def new_case_id(store: Store) -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    while True:
        case_id = f"c_{day}_{secrets.token_hex(3)}"
        if not store.case_exists(case_id):
            return case_id


def to_response(case: dict) -> dict:
    """Add the fields that are derived rather than stored."""
    return {
        **case,
        "image_url": f"/api/cases/{case['case_id']}/image",
        "disclaimer": DISCLAIMER,
    }


def create_app(
    predictor: Predictor | None = None,
    db_path: Path | None = None,
    uploads_dir: Path | None = None,
    thresholds: dict | None = None,
) -> FastAPI:
    predictor = predictor or load_predictor(ARTIFACTS)
    thresholds = thresholds or load_quality_thresholds()
    store = Store(db_path or Path(os.environ.get("RETINASCAN_DB", ROOT / "api" / "retinascan.db")))
    uploads = uploads_dir or Path(os.environ.get("RETINASCAN_UPLOADS", ROOT / "api" / "uploads"))
    uploads.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="RetinaScan XAI API", version=str(CONTRACT_VERSION))

    @app.middleware("http")
    async def reject_oversized_requests(request: Request, call_next):
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_REQUEST_BYTES:
            return error_response(413, "payload_too_large", "Image is larger than the 15 MB limit.")
        return await call_next(request)

    # The Mac frontend runs on another origin. No cookies are used.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, error: ApiError):
        return error_response(error.status, error.code, error.message)

    @app.exception_handler(CaseNotFound)
    async def handle_case_not_found(_: Request, error: CaseNotFound):
        return error_response(404, "not_found", f"Case {error} not found.")

    @app.exception_handler(DecisionNotAllowed)
    async def handle_decision_not_allowed(_: Request, __: DecisionNotAllowed):
        return error_response(409, "bad_request", "Retake cases have no prediction to review.")

    @app.exception_handler(ModelUnavailable)
    async def handle_model_unavailable(_: Request, error: ModelUnavailable):
        return error_response(503, "model_unavailable", str(error) or "Model is not available.")

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, error: RequestValidationError):
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'][1:]) or 'body'}: {item['msg']}"
            for item in error.errors()
        )
        return error_response(422, "validation_error", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, error: StarletteHTTPException):
        code = ERROR_CODES.get(error.status_code, "internal")
        return error_response(error.status_code, code, str(error.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, error: Exception):
        logger.exception("Unhandled error", exc_info=error)
        return error_response(500, "internal", "Something went wrong on the server.")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "contract_version": CONTRACT_VERSION, "model": predictor.health()}

    @app.post("/api/analyse", status_code=201)
    def analyse(
        image: UploadFile = File(...),
        patient_id: str | None = Form(None),
        eye: Literal["left", "right", "unknown"] = Form("unknown"),
    ):
        patient_id = (patient_id or "").strip()
        if len(patient_id) > MAX_PATIENT_ID_LENGTH:
            raise ApiError(422, f"patient_id: at most {MAX_PATIENT_ID_LENGTH} characters")

        data, suffix = read_upload(image)
        bgr = decode_bgr(data)
        quality_result = quality.check(bgr, thresholds)

        if quality_result["ok"]:
            result = predictor.predict(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        else:
            result = {
                "prediction": None,
                "recommendation": recommendation_for(None),
                "priority": priority_for(None),
                "evidence": None,
                "model": dict(predictor.model),
            }

        created_at = now_iso()
        case = {
            "case_id": new_case_id(store),
            "patient_id": patient_id or f"PHC-{created_at[:4]}-{store.next_patient_number():05d}",
            "eye": eye,
            "created_at": created_at,
            "status": "pending" if result["prediction"] else "retake",
            "quality": quality_result,
            "prediction": result["prediction"],
            "recommendation": result["recommendation"],
            "evidence": result["evidence"],
            "priority": result["priority"],
            "final_grade": None,
            "decisions": [],
            "model": result["model"],
        }

        image_path = uploads / f"{case['case_id']}{suffix}"
        image_path.write_bytes(data)
        try:
            store.add_case(case, image_path)
        except BaseException:
            image_path.unlink(missing_ok=True)
            raise
        return to_response(case)

    @app.get("/api/cases")
    def list_cases(
        status: Literal["pending", "reviewed", "retake", "all"] = "pending",
        limit: int = Query(50, ge=1, le=200),
    ):
        cases, total = store.list_cases(status, limit)
        for case in cases:
            case["image_url"] = f"/api/cases/{case['case_id']}/image"
        return {"cases": cases, "total": total}

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        return to_response(store.get_case(case_id))

    @app.post("/api/cases/{case_id}/decision")
    def decide(case_id: str, decision: DecisionIn):
        store.add_decision(
            case_id, decision.action, decision.final_grade, decision.reviewer, decision.note
        )
        return to_response(store.get_case(case_id))

    @app.get("/api/cases/{case_id}/image")
    def case_image(case_id: str):
        path = store.image_path(case_id)
        if not path.is_file():
            raise ApiError(404, "Image file is missing.")
        return FileResponse(path, media_type=MEDIA_TYPES[path.suffix])

    @app.get("/api/similar/{id_code}.jpg")
    def similar_image(id_code: str):
        data = predictor.thumbnail(id_code) if SAFE_ID.match(id_code) else None
        if data is None:
            raise ApiError(404, "Similar case image not found.")
        return Response(data, media_type="image/jpeg")

    @app.get("/api/operating-curve")
    def operating_curve():
        return predictor.operating_curve()

    return app


app = create_app()
