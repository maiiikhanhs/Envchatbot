from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

import requests

from app.config import (
    COMFYUI_BASE_URL,
    COMFYUI_FINAL_OUTPUT_NODE_TITLE,
    COMFYUI_INPUT_CONTEXT_NODE_TITLE,
    COMFYUI_INPUT_QUESTION_NODE_TITLE,
    COMFYUI_LLM_API_KEY,
    COMFYUI_POLL_INTERVAL,
    COMFYUI_QUESTION_SELECTOR_NODE_TITLE,
    COMFYUI_RESOLVED_QUESTION_OUTPUT_NODE_TITLE,
    COMFYUI_ROUTER_OUTPUT_NODE_TITLE,
    COMFYUI_TIMEOUT,
    COMFYUI_WORKFLOW_PATH,
)

INPUT_NODE_TYPE = "get_string"
OUTPUT_NODE_TYPE = "PreviewAny"
QUESTION_SELECTOR_NODE_TYPE = "any_switcher"
COMFYUI_LLM_API_KEY_PLACEHOLDER = "${COMFYUI_LLM_API_KEY}"


def load_workflow(workflow_path: str | None = None) -> dict:
    target_path = Path(workflow_path or COMFYUI_WORKFLOW_PATH)
    with target_path.open("r", encoding="utf-8") as workflow_file:
        workflow = json.load(workflow_file)
    return inject_workflow_secrets(workflow)


def inject_workflow_secrets(workflow: dict) -> dict:
    if not COMFYUI_LLM_API_KEY:
        return workflow

    serialized = json.dumps(workflow)
    if COMFYUI_LLM_API_KEY_PLACEHOLDER not in serialized:
        return workflow

    return json.loads(serialized.replace(COMFYUI_LLM_API_KEY_PLACEHOLDER, COMFYUI_LLM_API_KEY))


def _resolve_node_id_by_title(
    workflow: dict,
    *,
    title: str,
    expected_type: str,
) -> int:
    nodes = workflow.get("nodes", [])
    matches = [node for node in nodes if node.get("title") == title]

    if not matches:
        raise ValueError(f"Workflow node '{title}' was not found.")
    if len(matches) > 1:
        raise ValueError(f"Workflow node '{title}' must be unique, found {len(matches)}.")

    node = matches[0]
    node_type = node.get("type")
    if node_type != expected_type:
        raise ValueError(
            f"Workflow node '{title}' must have type '{expected_type}', got '{node_type}'."
        )

    return int(node["id"])


def _resolve_workflow_node_ids(workflow: dict) -> dict[str, int]:
    node_ids = {
        "question_input_id": _resolve_node_id_by_title(
            workflow,
            title=COMFYUI_INPUT_QUESTION_NODE_TITLE,
            expected_type=INPUT_NODE_TYPE,
        ),
        "context_input_id": _resolve_node_id_by_title(
            workflow,
            title=COMFYUI_INPUT_CONTEXT_NODE_TITLE,
            expected_type=INPUT_NODE_TYPE,
        ),
        "router_output_id": _resolve_node_id_by_title(
            workflow,
            title=COMFYUI_ROUTER_OUTPUT_NODE_TITLE,
            expected_type=OUTPUT_NODE_TYPE,
        ),
        "final_output_id": _resolve_node_id_by_title(
            workflow,
            title=COMFYUI_FINAL_OUTPUT_NODE_TITLE,
            expected_type=OUTPUT_NODE_TYPE,
        ),
    }

    for optional_key, title, expected_type in (
        ("resolved_question_output_id", COMFYUI_RESOLVED_QUESTION_OUTPUT_NODE_TITLE, OUTPUT_NODE_TYPE),
        ("question_selector_node_id", COMFYUI_QUESTION_SELECTOR_NODE_TITLE, QUESTION_SELECTOR_NODE_TYPE),
    ):
        try:
            node_ids[optional_key] = _resolve_node_id_by_title(
                workflow,
                title=title,
                expected_type=expected_type,
            )
        except ValueError:
            node_ids[optional_key] = 0

    return node_ids


def inject_workflow_inputs(
    workflow: dict,
    *,
    question: str,
    context: str,
    question_source_index: int = 1,
    question_node_id: int,
    context_node_id: int,
    question_selector_node_id: int = 0,
) -> dict:
    updated_workflow = json.loads(json.dumps(workflow))

    for node in updated_workflow.get("nodes", []):
        if node.get("id") == question_node_id:
            node["widgets_values"] = [question]
        if node.get("id") == context_node_id:
            node["widgets_values"] = [context]
        if question_selector_node_id and node.get("id") == question_selector_node_id:
            node["widgets_values"] = [question_source_index]

    return updated_workflow


def convert_workflow_to_prompt(workflow: dict) -> dict:
    links = workflow.get("links", [])
    link_map = {link[0]: link for link in links}
    prompt = {}

    for node in workflow.get("nodes", []):
        node_id = str(node["id"])
        inputs = {}
        widget_index = 0
        widget_values = node.get("widgets_values", [])

        for input_definition in node.get("inputs", []):
            input_name = input_definition["name"]
            link_id = input_definition.get("link")
            has_widget = input_definition.get("widget") is not None
            widget_value = None

            if has_widget and widget_index < len(widget_values):
                widget_value = widget_values[widget_index]
                widget_index += 1

            if link_id is not None:
                link_data = link_map.get(link_id)
                if link_data is None:
                    continue
                source_node_id = str(link_data[1])
                source_output_slot = link_data[2]
                inputs[input_name] = [source_node_id, source_output_slot]
                continue

            if has_widget:
                inputs[input_name] = widget_value

        prompt[node_id] = {
            "class_type": node["type"],
            "inputs": inputs,
            "_meta": {"title": node.get("title", node["type"])},
        }

    return prompt


def queue_prompt(prompt: dict) -> dict:
    payload = {
        "client_id": str(uuid.uuid4()),
        "prompt": prompt,
    }
    response = requests.post(
        f"{COMFYUI_BASE_URL}/prompt",
        json=payload,
        timeout=COMFYUI_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def poll_history(prompt_id: str, timeout: int = COMFYUI_TIMEOUT) -> dict:
    started_at = time.time()

    while time.time() - started_at < timeout:
        response = requests.get(
            f"{COMFYUI_BASE_URL}/history/{prompt_id}",
            timeout=COMFYUI_TIMEOUT,
        )
        response.raise_for_status()
        history = response.json()

        if prompt_id in history:
            return history[prompt_id]

        time.sleep(COMFYUI_POLL_INTERVAL)

    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def _extract_first_string(value) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        for item in value:
            extracted = _extract_first_string(item)
            if extracted:
                return extracted
        return ""

    return ""


def extract_preview_text(history_payload: dict, node_id: int) -> str:
    node_output = history_payload.get("outputs", {}).get(str(node_id), {})
    direct_text = _extract_first_string(node_output.get("text", []))

    if direct_text:
        return direct_text

    ui_payload = node_output.get("ui", {})
    text_payload = _extract_first_string(ui_payload.get("text", []))

    if text_payload:
        return text_payload

    result_payload = _extract_first_string(node_output.get("result", []))
    if result_payload:
        return result_payload

    return ""


def _extract_execution_ms(history_payload: dict) -> int:
    messages = (history_payload.get("status") or {}).get("messages") or []
    started_at = None
    finished_at = None

    for message in messages:
        if not isinstance(message, list) or len(message) < 2:
            continue
        event_name, payload = message[0], message[1] or {}
        if event_name == "execution_start":
            started_at = payload.get("timestamp")
        if event_name == "execution_success":
            finished_at = payload.get("timestamp")

    if isinstance(started_at, int) and isinstance(finished_at, int):
        return max(0, finished_at - started_at)
    return 0


def run_comfyui_workflow(
    *,
    question: str,
    context: str,
    question_source_index: int = 1,
    workflow_path: str | None = None,
) -> dict:
    started_at = time.perf_counter()
    workflow = load_workflow(workflow_path)
    node_ids = _resolve_workflow_node_ids(workflow)
    workflow = inject_workflow_inputs(
        workflow,
        question=question,
        context=context,
        question_source_index=question_source_index,
        question_node_id=node_ids["question_input_id"],
        context_node_id=node_ids["context_input_id"],
        question_selector_node_id=node_ids.get("question_selector_node_id", 0),
    )
    prompt = convert_workflow_to_prompt(workflow)
    queue_started_at = time.perf_counter()
    queue_result = queue_prompt(prompt)
    queued_at = time.perf_counter()
    prompt_id = queue_result["prompt_id"]
    history = poll_history(prompt_id)
    finished_at = time.perf_counter()

    print(
        "[LATENCY] comfyui "
        f"prompt_id={prompt_id} "
        f"queue_ms={int((queued_at - queue_started_at) * 1000)} "
        f"poll_ms={int((finished_at - queued_at) * 1000)} "
        f"total_ms={int((finished_at - started_at) * 1000)} "
        f"execution_ms={_extract_execution_ms(history)}"
    )

    final_output = extract_preview_text(history, node_ids["final_output_id"])
    router_output = extract_preview_text(history, node_ids["router_output_id"])
    resolved_question = ""
    if node_ids.get("resolved_question_output_id"):
        resolved_question = extract_preview_text(history, node_ids["resolved_question_output_id"])

    return {
        "status": "success",
        "prompt_id": prompt_id,
        "router_output": router_output,
        "final_output": final_output,
        "resolved_question": resolved_question,
        "history": history,
    }
