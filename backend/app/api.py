"""FastAPI server exposing the chatbot preprocessing + ComfyUI pipeline."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import BACKEND_ROOT
from app.database.mongo import (
    CONVERSATIONS_COLLECTION,
    MESSAGES_COLLECTION,
    ensure_mongo_indexes,
    get_collection,
)
from app.services.auth_service import (
    ensure_users_indexes,
    login_user,
    register_user,
    seed_default_users,
)
from app.services.chat_service import process_chat_request
from app.services.knowledge_sync_service import (
    KnowledgeSyncError,
    inspect_faiss_index,
    list_knowledge_chunks,
    list_knowledge_documents,
    sync_faiss_to_mongo,
)
from app.services.report_service import (
    ReportValidationError,
    create_report,
    list_reports,
    update_report_status,
)

UPLOAD_DIR = BACKEND_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="EnvChat API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup ─────────────────────────────────────────────────────────


@app.on_event("startup")
def on_startup():
    ensure_mongo_indexes()
    ensure_users_indexes()
    seed_default_users()


def _serialize_mongo_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Health ──────────────────────────────────────────────────────────


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "envchat-api"}


# ── Auth ────────────────────────────────────────────────────────────


from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ReportStatusRequest(BaseModel):
    status: str
    note: str = ""


class KnowledgeSyncRequest(BaseModel):
    index_path: str = ""


@app.post("/api/register")
def api_register(body: RegisterRequest):
    result = register_user(body.username, body.password)
    if result["status"] == "error":
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/login")
def api_login(body: LoginRequest):
    result = login_user(body.username, body.password)
    if result["status"] == "error":
        return JSONResponse(status_code=401, content=result)
    return result


# ── Knowledge Base Management ───────────────────────────────────────


@app.get("/api/knowledge/faiss/inspect")
def api_inspect_faiss(index_path: str = ""):
    try:
        return inspect_faiss_index(index_path=index_path)
    except KnowledgeSyncError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})


@app.post("/api/knowledge/faiss/sync")
def api_sync_faiss(body: KnowledgeSyncRequest):
    try:
        return sync_faiss_to_mongo(index_path=body.index_path)
    except KnowledgeSyncError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})


@app.get("/api/knowledge/documents")
def api_list_knowledge_documents(limit: int = 100, skip: int = 0):
    return {
        "status": "success",
        "documents": list_knowledge_documents(limit=limit, skip=skip),
    }


@app.get("/api/knowledge/documents/{document_id}/chunks")
def api_list_knowledge_chunks(document_id: str, limit: int = 100, skip: int = 0):
    return {
        "status": "success",
        "chunks": list_knowledge_chunks(document_id=document_id, limit=limit, skip=skip),
    }


# ── Reports ─────────────────────────────────────────────────────────


@app.post("/api/reports")
def submit_report(
    report_type: str = Form(...),
    content: str = Form(...),
    conversation_id: str = Form(""),
    message_id: str = Form(""),
    client_context: str = Form(""),
    attachment: UploadFile | None = File(None),
    x_user_id: str = Header(default=""),
):
    try:
        return create_report(
            report_type=report_type,
            content=content,
            user_id=x_user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            client_context=client_context,
            attachment=attachment,
        )
    except ReportValidationError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(exc)})


@app.get("/api/reports")
def api_list_reports(
    status: str = "",
    report_type: str = "",
    limit: int = 50,
    skip: int = 0,
):
    return {
        "status": "success",
        "reports": list_reports(status=status, report_type=report_type, limit=limit, skip=skip),
    }


@app.patch("/api/reports/{report_id}/status")
def api_update_report_status(report_id: str, body: ReportStatusRequest):
    try:
        result = update_report_status(report_id, body.status, body.note)
    except ReportValidationError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})
    if result["status"] == "error":
        return JSONResponse(status_code=404, content=result)
    return result


# ── Chat ────────────────────────────────────────────────────────────


@app.post("/api/chat")
def chat(
    question: str = Form(...),
    session_id: str = Form(""),
    file: UploadFile | None = File(None),
    x_user_id: str = Header(default=""),
):
    # Generate session_id if not provided
    if not session_id.strip():
        session_id = str(uuid.uuid4())

    # Handle optional file upload
    file_path: str | None = None
    if file and file.filename:
        safe_name = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = str(UPLOAD_DIR / safe_name)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    try:
        result = process_chat_request(
            question=question,
            file_path=file_path,
            original_filename=file.filename if file and file.filename else "",
            session_id=session_id,
            user_id=x_user_id,
        )

        router_label = result.get("router_output", "")
        answer = ""
        if result.get("comfyui_result", {}).get("status") == "success":
            answer = result["comfyui_result"].get("final_output", "")
        retrieved_chunks = result.get("retrieved_chunks", [])

        return {
            "status": result.get("status", "error"),
            "conversation_id": result.get("conversation_id", ""),
            "session_id": session_id,
            "question": result.get("question", question),
            "answer": answer,
            "router_label": router_label,
            "input_type": result.get("input_type", "text_only"),
            "retrieved_count": len(retrieved_chunks),
            "retrieved_chunks": retrieved_chunks,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc)},
        )
    finally:
        # Cleanup uploaded file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# ── Conversations ───────────────────────────────────────────────────


@app.get("/api/conversations")
def list_conversations(
    limit: int = 50, skip: int = 0, x_user_id: str = Header(default="")
):
    query = {"user_id": x_user_id} if x_user_id else {}
    cursor = (
        get_collection(CONVERSATIONS_COLLECTION)
        .find(query)
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
    )
    conversations = [_serialize_mongo_doc(doc) for doc in cursor]
    return {"status": "success", "conversations": conversations}


@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, x_user_id: str = Header(default="")):
    # Depending on auth restrictiveness, we could enforce that conversation_id belongs to x_user_id.
    # For now, just fetching by conversation ID is safe if IDs are non-guessable.
    cursor = (
        get_collection(MESSAGES_COLLECTION)
        .find({"conversation_id": conversation_id})
        .sort("created_at", 1)
    )
    messages = [_serialize_mongo_doc(doc) for doc in cursor]
    return {"status": "success", "messages": messages}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, x_user_id: str = Header(default="")):
    from bson import ObjectId

    # Delete conversation. Optional: enforce ownership by including user_id in the query.
    query = {"_id": ObjectId(conversation_id)}
    if x_user_id:
        query["user_id"] = x_user_id

    result = get_collection(CONVERSATIONS_COLLECTION).delete_one(query)
    
    # Only delete messages if the conversation was successfully deleted (ownership confirmed)
    if result.deleted_count > 0:
        get_collection(MESSAGES_COLLECTION).delete_many(
            {"conversation_id": conversation_id}
        )
        
    return {"status": "success"}
