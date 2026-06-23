from __future__ import annotations

"""Input preprocessing for the ComfyUI-facing workflow layer."""

from app.input.file_reader import (
    FileExtractionError,
    FileNotFoundCustomError,
    UnsupportedFileTypeError,
    extract_file_content,
)
from app.models.schemas import (
    ERROR_FILE_NOT_FOUND,
    ERROR_FILE_ONLY_NOT_ALLOWED,
    ERROR_FILE_TEXT_EXTRACTION_FAILED,
    ERROR_INTERNAL_PROCESSING,
    ERROR_MISSING_QUESTION,
    ERROR_UNSUPPORTED_FILE_TYPE,
    INPUT_TYPE_INVALID,
    INPUT_TYPE_TEXT_ONLY,
    INPUT_TYPE_TEXT_WITH_FILE,
)


def validate_input(question, file_path=None):
    """Validate that preprocessing only receives text_only or text_with_file input."""
    normalized_question = normalize_question(question)

    if not normalized_question:
        if file_path:
            raise ValueError(ERROR_FILE_ONLY_NOT_ALLOWED)
        raise ValueError(ERROR_MISSING_QUESTION)

    return True


def detect_input_type(question, file_path=None):
    """Return the supported preprocessing input type."""
    normalized_question = normalize_question(question)

    if not normalized_question:
        return INPUT_TYPE_INVALID

    if file_path:
        return INPUT_TYPE_TEXT_WITH_FILE

    return INPUT_TYPE_TEXT_ONLY


def normalize_question(question):
    """Normalize the question into a stable value for downstream workflow input."""
    if question is None:
        return ""

    normalized = " ".join(str(question).split())
    return normalized.strip()


def build_success_response(
    *,
    input_type,
    user_question,
    normalized_question,
    has_file,
    file_info=None,
    file_content="",
):
    """Build a stable preprocessing payload for the next pipeline step."""
    prepared_context = {
        "question": normalized_question,
        "file_content": file_content,
        "combined_context": (
            f"Question: {normalized_question}\n\nFile Content:\n{file_content}"
            if has_file
            else normalized_question
        ),
    }

    return {
        "status": "success",
        "input_type": input_type,
        "user_question": user_question,
        "normalized_question": normalized_question,
        "has_file": has_file,
        "file_info": file_info,
        "file_content": file_content,
        "prepared_context": prepared_context,
        "error_code": None,
        "error_message": None,
    }


def build_error_response(
    *,
    error_code,
    error_message,
    user_question,
    normalized_question="",
    has_file=False,
    file_info=None,
    file_content="",
):
    """Build a stable error payload for preprocessing failures."""
    prepared_context = {
        "question": normalized_question,
        "file_content": file_content,
        "combined_context": "",
    }

    return {
        "status": "error",
        "input_type": INPUT_TYPE_INVALID,
        "user_question": user_question,
        "normalized_question": normalized_question,
        "has_file": has_file,
        "file_info": file_info,
        "file_content": file_content,
        "prepared_context": prepared_context,
        "error_code": error_code,
        "error_message": error_message,
    }


def prepare_chatbot_input(question, file_path=None):
    """Prepare normalized input and optional file content before chunking/retrieval."""
    user_question = question
    normalized_question = normalize_question(question)
    has_file = bool(file_path)

    try:
        validate_input(question, file_path)
        input_type = detect_input_type(question, file_path)

        if input_type == INPUT_TYPE_TEXT_ONLY:
            return build_success_response(
                input_type=input_type,
                user_question=user_question,
                normalized_question=normalized_question,
                has_file=False,
                file_info=None,
                file_content="",
            )

        file_info, file_content = extract_file_content(file_path)
        return build_success_response(
            input_type=input_type,
            user_question=user_question,
            normalized_question=normalized_question,
            has_file=True,
            file_info=file_info,
            file_content=file_content,
        )
    except ValueError as exc:
        error_code = str(exc)
        return build_error_response(
            error_code=error_code,
            error_message=error_code,
            user_question=user_question,
            normalized_question=normalized_question,
            has_file=has_file,
        )
    except FileNotFoundCustomError as exc:
        return build_error_response(
            error_code=ERROR_FILE_NOT_FOUND,
            error_message=str(exc),
            user_question=user_question,
            normalized_question=normalized_question,
            has_file=has_file,
        )
    except UnsupportedFileTypeError as exc:
        return build_error_response(
            error_code=ERROR_UNSUPPORTED_FILE_TYPE,
            error_message=str(exc),
            user_question=user_question,
            normalized_question=normalized_question,
            has_file=has_file,
        )
    except FileExtractionError as exc:
        return build_error_response(
            error_code=ERROR_FILE_TEXT_EXTRACTION_FAILED,
            error_message=str(exc),
            user_question=user_question,
            normalized_question=normalized_question,
            has_file=has_file,
        )
    except Exception as exc:
        return build_error_response(
            error_code=ERROR_INTERNAL_PROCESSING,
            error_message=str(exc),
            user_question=user_question,
            normalized_question=normalized_question,
            has_file=has_file,
        )
