import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from models.schemas import Requirement, RequirementBatch, VerificationResult
from services.graph_builder import graph_builder

router = APIRouter(prefix="/requirements", tags=["requirements"])

_store: dict[str, Requirement] = {}

DATA_PATH = Path(__file__).parent.parent / "data" / "sample_requirements.json"


@router.get("/sample", response_model=list[Requirement])
def get_sample_requirements():
    """Load the built-in sample parking requirements dataset."""
    raw = json.loads(DATA_PATH.read_text())
    return [Requirement(**r) for r in raw]


@router.get("/", response_model=list[Requirement])
def list_requirements():
    return list(_store.values())


@router.post("/", response_model=Requirement)
def add_requirement(req: Requirement):
    _store[req.id] = req
    return req


@router.post("/batch", response_model=list[Requirement])
def add_batch(batch: RequirementBatch):
    for req in batch.requirements:
        _store[req.id] = req
    return batch.requirements


@router.get("/{req_id}", response_model=Requirement)
def get_requirement(req_id: str):
    if req_id not in _store:
        raise HTTPException(404, detail=f"Requirement {req_id} not found")
    return _store[req_id]


@router.post("/verify/{req_id}", response_model=VerificationResult)
def verify_requirement(req_id: str):
    if req_id not in _store:
        raise HTTPException(404, detail=f"Requirement {req_id} not found")
    return graph_builder.verify_requirement(_store[req_id])


@router.post("/verify-all", response_model=list[VerificationResult])
def verify_all():
    return [graph_builder.verify_requirement(r) for r in _store.values()]
