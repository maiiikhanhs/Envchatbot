import os
from pathlib import Path

SUPPORTED_FILE_EXTENSIONS = {".pdf", ".docx"}
MIN_EXTRACTED_TEXT_LENGTH = 1

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27019")
MONGODB_FALLBACK_URI = os.getenv("MONGODB_FALLBACK_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "chatbot_datn")

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "env_document_chunks")

SEMANTIC_ANSWER_CACHE_ENABLED = os.getenv("SEMANTIC_ANSWER_CACHE_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SEMANTIC_ANSWER_CACHE_COLLECTION = os.getenv(
    "SEMANTIC_ANSWER_CACHE_COLLECTION",
    "env_answer_cache_semantic",
)
SEMANTIC_ANSWER_CACHE_MIN_SIMILARITY = float(
    os.getenv("SEMANTIC_ANSWER_CACHE_MIN_SIMILARITY", "0.88")
)
SEMANTIC_ANSWER_CACHE_VERIFIER_MIN_CONFIDENCE = float(
    os.getenv("SEMANTIC_ANSWER_CACHE_VERIFIER_MIN_CONFIDENCE", "0.90")
)
SEMANTIC_ANSWER_CACHE_VERIFIER_URL = os.getenv("SEMANTIC_ANSWER_CACHE_VERIFIER_URL", "")
SEMANTIC_ANSWER_CACHE_VERIFIER_API_KEY = os.getenv(
    "SEMANTIC_ANSWER_CACHE_VERIFIER_API_KEY",
    "",
)
SEMANTIC_ANSWER_CACHE_VERIFIER_MODEL = os.getenv(
    "SEMANTIC_ANSWER_CACHE_VERIFIER_MODEL",
    "",
)
SEMANTIC_ANSWER_CACHE_VERIFIER_TIMEOUT = float(
    os.getenv("SEMANTIC_ANSWER_CACHE_VERIFIER_TIMEOUT", "4")
)
TEXT_WITH_FILE_ANSWER_CACHE_ENABLED = os.getenv(
    "TEXT_WITH_FILE_ANSWER_CACHE_ENABLED",
    "false",
).lower() in {
    "1",
    "true",
    "yes",
    "on",
}

COMFYUI_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
COMFYUI_LLM_API_KEY = os.getenv("COMFYUI_LLM_API_KEY", "")
COMFYUI_TIMEOUT = int(os.getenv("COMFYUI_TIMEOUT", "300"))
COMFYUI_POLL_INTERVAL = float(os.getenv("COMFYUI_POLL_INTERVAL", "2"))
COMFYUI_WORKFLOW_PATH = os.getenv(
    "COMFYUI_WORKFLOW_PATH",
    str(BACKEND_ROOT / "workflows" / "comfyui" / "EnvironmentChatbot.json"),
)
COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH = os.getenv(
    "COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH",
    str(BACKEND_ROOT / "workflows" / "comfyui" / "Environment(1)Chatbot.json"),
)
COMFYUI_EMBEDDED_PYTHON_PATH = os.getenv(
    "COMFYUI_EMBEDDED_PYTHON_PATH",
    str(PROJECT_ROOT / "ComfyUI_windows_portable" / "python_embeded" / "python.exe"),
)
COMFYUI_FAISS_KB_PATH = os.getenv(
    "COMFYUI_FAISS_KB_PATH",
    str(
        PROJECT_ROOT
        / "ComfyUI_windows_portable"
        / "ComfyUI"
        / "Environment_KNOWLEDGE_BASE_NHA_NUOC"
    ),
)
COMFYUI_FAISS_EMBEDDING_MODEL = os.getenv(
    "COMFYUI_FAISS_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
COMFYUI_INPUT_QUESTION_NODE_TITLE = os.getenv(
    "COMFYUI_INPUT_QUESTION_NODE_TITLE",
    "Input Question",
)
COMFYUI_INPUT_CONTEXT_NODE_TITLE = os.getenv(
    "COMFYUI_INPUT_CONTEXT_NODE_TITLE",
    "Input Context",
)
COMFYUI_INPUT_FORCED_ROUTER_LABEL_NODE_TITLE = os.getenv(
    "COMFYUI_INPUT_FORCED_ROUTER_LABEL_NODE_TITLE",
    "Forced Router Label",
)
COMFYUI_ROUTER_OUTPUT_NODE_TITLE = os.getenv(
    "COMFYUI_ROUTER_OUTPUT_NODE_TITLE",
    "Router Output",
)
COMFYUI_FINAL_OUTPUT_NODE_TITLE = os.getenv(
    "COMFYUI_FINAL_OUTPUT_NODE_TITLE",
    "Final Output",
)
COMFYUI_RESOLVED_QUESTION_OUTPUT_NODE_TITLE = os.getenv(
    "COMFYUI_RESOLVED_QUESTION_OUTPUT_NODE_TITLE",
    "Resolved Question Output",
)
COMFYUI_QUESTION_SELECTOR_NODE_TITLE = os.getenv(
    "COMFYUI_QUESTION_SELECTOR_NODE_TITLE",
    "Question Selector",
)
