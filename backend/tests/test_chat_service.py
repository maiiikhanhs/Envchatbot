from __future__ import annotations



import json

from pathlib import Path



from unittest.mock import ANY





import app.services.chat_service as chat_service
import app.services.chat_text_only_service as text_only_service
import app.services.chat_text_with_file_service as text_with_file_service
from app.services.text_with_file.assessment import (
    build_file_vs_kb_workflow_question,
)


def test_sanitize_final_response_preserves_markdown_newlines():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_SUMMARY",
        final_answer="  - Dòng 1  \n\n\n  - Dòng 2\tcó tab  ",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == "- Dòng 1\n\n- Dòng 2 có tab"
    assert router_label == "FILE_SUMMARY"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_final_response_strips_thought_blocks_before_ui():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_VS_KB",
        final_answer=(
            "<thought>nội bộ không được lộ</thought>\n"
            "**Kết luận**\n"
            "- Có 1 chỉ tiêu không đạt.\n"
        ),
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert "<thought" not in answer.lower()
    assert "nội bộ" not in answer
    assert answer == "**Kết luận**\n- Có 1 chỉ tiêu không đạt."
    assert router_label == "FILE_VS_KB"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_final_response_removes_runtime_error_lines_but_keeps_table():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_VS_KB",
        final_answer=(
            "Error code: 503 - model overloaded\n"
            "| Chỉ tiêu | Kết luận |\n"
            "| --- | --- |\n"
            "| COD | Không đạt |\n"
        ),
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert "Error code" not in answer
    assert "| COD | Không đạt |" in answer
    assert router_label == "FILE_VS_KB"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_final_response_normalizes_latex_symbols_for_display():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_VS_KB",
        final_answer=(
            "**Dữ liệu trong file**\n"
            r"- Thông số $\text{SO}_2$ có giá trị ghi nhận là $118 \mu\text{g/Nm}^3$ ."
            "\n\n"
            "| Thông số | Giá trị | Đơn vị |\n"
            "| --- | --- | --- |\n"
            r"| SO_{2} | 118 | \mu g/Nm^3 |"
        ),
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert "SO2" in answer
    assert "118 µg/Nm3" in answer
    assert "| SO2 | 118 | µg/Nm3 |" in answer
    for forbidden in ("$", "\\text", "\\mu", "_{", "}^", "^{"):
        assert forbidden not in answer
    assert router_label == "FILE_VS_KB"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_final_response_normalizes_source_markers_without_losing_underscore():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_VS_KB",
        final_answer=(
            "**Căn cứ đối chiếu**\n"
            "- Theo [SOURCE1], [SOURCE 8], [FILESOURCE2] và [FILE SOURCE 3].\n"
            "- Chỉ tiêu SO_{2} vẫn phải hiển thị là SO2."
        ),
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert "[SOURCE_1]" in answer
    assert "[SOURCE_8]" in answer
    assert "[FILE_SOURCE_2]" in answer
    assert "[FILE_SOURCE_3]" in answer
    assert "[SOURCE1]" not in answer
    assert "SO2" in answer
    assert router_label == "FILE_VS_KB"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_file_vs_kb_workflow_question_includes_assessment_signals():
    question = build_file_vs_kb_workflow_question(
        original_question="Dựa trên file tôi vừa upload, hãy đánh giá hồ sơ quan trắc này đạt hay chưa đạt.",
        refined_context=(
            "=== FILE UPLOAD ===\n\n"
            "Question: Dựa trên file tôi vừa upload, hãy đánh giá hồ sơ quan trắc này đạt hay chưa đạt.\n\n"
            "Relevant Context:\n"
            "[FILE_SOURCE_1] Mã hồ sơ: TC-001\n"
            "Quy chuẩn tham chiếu: QCVN 05:2023/BTNMT.\n"
            "Thông số quan trắc: SO2 | Trung bình 24 giờ | 118 | µg/Nm3.\n"
        ),
        retrieved_chunks=[],
    )

    assert "QCVN 05:2023/BTNMT" in question
    assert "SO2" in question
    assert "Trung bình 24 giờ" in question
    assert "118" in question
    assert "µg/Nm3" in question
    assert "giới hạn" in question
    assert "Đạt/Chưa đạt" in question


def test_file_vs_kb_workflow_question_includes_tc017_ph_signals():
    question = build_file_vs_kb_workflow_question(
        original_question="Dựa trên file tôi vừa upload, hãy đánh giá hồ sơ quan trắc này đạt hay chưa đạt.",
        refined_context="",
        file_content=(
            "Hồ sơ quan trắc TC-017\n"
            "Bối cảnh lấy mẫu: Mẫu NT-SH-03, cột A, hệ số K = 1.\n"
            "Mã hồ sơ | TC-017\n"
            "Nhóm dữ liệu | Nước thải sinh hoạt\n"
            "Quy chuẩn tham chiếu | QCVN 14:2008/BTNMT\n"
            "Phạm vi áp dụng | Nguồn tiếp nhận áp dụng cột A.\n"
            "Thông số | Kỳ đo / mô tả mẫu | Giá trị ghi nhận | Đơn vị\n"
            "pH | Mẫu đơn | 4.9 | -\n"
        ),
        retrieved_chunks=[],
    )

    assert "QCVN 14:2008/BTNMT" in question
    assert "pH" in question
    assert "cột A" in question
    assert "4.9" in question
    assert "bảng" in question
    assert "Bảng 1" not in question
    assert "khoảng giá trị" in question


def test_file_vs_kb_workflow_question_keeps_effective_date_signals_without_fixed_limits():
    question = build_file_vs_kb_workflow_question(
        original_question="đánh giá đạt hay chưa đạt",
        refined_context="",
        file_content=(
            "Quy chuẩn tham chiếu | QCVN 05:2023/BTNMT\n"
            "Ngày đo | 2026-03-20\n"
            "Thông tin hiệu lực | áp dụng từ ngày 2026-01-01\n"
            "PM2,5 | Trung bình 24 giờ | 48 | µg/Nm3\n"
        ),
        retrieved_chunks=[],
    )

    assert "QCVN 05:2023/BTNMT" in question
    assert "PM2,5" in question
    assert "2026-03-20" in question
    assert "2026-01-01" in question
    assert "ghi chú" in question
    assert "hiệu lực" in question
    assert "45(*)" not in question


def test_file_vs_kb_workflow_question_does_not_truncate_muc_phan_loai_as_muc_ph():
    question = build_file_vs_kb_workflow_question(
        original_question="đánh giá đạt hay chưa đạt",
        refined_context="",
        file_content=(
            "Quy chuẩn tham chiếu | QCVN 08:2023/BTNMT\n"
            "Mức phân loại mục tiêu: B\n"
            "pH | Mẫu đơn | 7.2 | -\n"
            "BOD5 | Mẫu đơn | 5.8 | mg/L\n"
            "COD | Mẫu đơn | 14 | mg/L\n"
            "DO | Mẫu đơn | 5.1 | mg/L\n"
        ),
        retrieved_chunks=[],
    )

    assert "Mức phân loại mục tiêu: B" in question
    assert "Mức ph;" not in question
    assert "Mức ph." not in question
    assert "pH; BOD5; COD; DO" in question


def test_file_vs_kb_workflow_question_does_not_infer_ph_from_pham_vi_or_code_number():
    question = build_file_vs_kb_workflow_question(
        original_question="đánh giá đạt hay chưa đạt",
        refined_context="",
        file_content=(
            "Quy chuẩn tham chiếu | QCVN 05:2023/BTNMT\n"
            "Phạm vi áp dụng | Không khí xung quanh.\n"
            "Mã mẫu | KK-PM25-01\n"
            "PM2,5 | Trung bình 24 giờ | 48 | µg/Nm3\n"
        ),
        retrieved_chunks=[],
    )

    assert "Thông số cần tra giới hạn: PM2,5." in question
    assert "Thông số cần tra giới hạn: PM2,5; pH." not in question
    assert "Dữ liệu đo trong file: PM2,5 | Trung bình 24 giờ | 48 | µg/Nm3." in question
    assert "KK-PM25-01" not in question


def test_file_vs_kb_workflow_question_returns_original_when_no_assessment_signal():
    original_question = "tài liệu này nói gì?"

    assert (
        build_file_vs_kb_workflow_question(
            original_question=original_question,
            refined_context="=== FILE UPLOAD ===\n[FILE_SOURCE_1] Nội dung mô tả chung.",
            retrieved_chunks=[],
        )
        == original_question
    )


def test_sanitize_final_response_removes_nonetype_type_error_line():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output="PHAP_LY",
        final_answer=(
            "expected string or bytes-like object, got 'NoneType'\n"
            "Tóm tắt quy chuẩn kỹ thuật quốc gia về tiếng ồn:\n"
            "- Mã quy chuẩn: QCVN 26:2010/BTNMT.\n"
        ),
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert "expected string" not in answer
    assert "NoneType" not in answer
    assert "QCVN 26:2010/BTNMT" in answer
    assert router_label == "PHAP_LY"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_final_response_repairs_source_marker_grammar_gap():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output="PHAP_LY",
        final_answer="Căn cứ theo về QCVN 26:2010/BTNMT, quy chuẩn này quy định tiếng ồn.",
        retrieved_chunks=[],
    )

    assert answer == "Căn cứ theo QCVN 26:2010/BTNMT, quy chuẩn này quy định tiếng ồn."
    assert router_label == "PHAP_LY"
    assert chunks == []


def test_sanitize_final_response_rejects_text_with_file_none_literal():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_VS_KB",
        final_answer="None",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == chat_service.TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK
    assert router_label == ""
    assert chunks == []


def test_sanitize_final_response_keeps_complete_text_with_file_insufficient_answer():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_with_file",
        router_output="FILE_VS_KB",
        final_answer=(
            "**Kết luận**\n"
            "- Chưa đủ căn cứ. KB chưa có giới hạn tương ứng với điều kiện áp dụng trong file.\n\n"
            "**Dữ liệu trong file**\n"
            "- pH, cột A: 4.9.\n\n"
            "**Căn cứ đối chiếu**\n"
            "- Chưa tìm thấy giới hạn tương ứng trong KB.\n\n"
            "**Nhận xét**\n"
            "- Thiếu giới hạn đối chiếu nên workflow chưa thể kết luận Đạt hoặc Chưa đạt."
        ),
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer.startswith("**Kết luận**")
    assert "Chưa đủ căn cứ" in answer
    assert router_label == "FILE_VS_KB"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_text_with_file_ignores_cache_and_runs_workflow():
    prepare_calls = []
    workflow_calls = []

    def fake_prepare_runtime(**kwargs):
        prepare_calls.append(kwargs)
        return {
            "status": "success",
            "file_id": "document-1",
            "active_file_name": "sample.docx",
            "active_file_source": "uploaded_now",
            "text_with_file_mode": "FILE_VS_KB",
            "refined_context": "File Context",
            "retrieved_chunks": [{"chunk_id": "chunk-1"}],
            "active_document": None,
        }

    result = text_with_file_service.handle_text_with_file_request(
        normalized_question="file này có phù hợp QCVN 40 không",
        effective_question="file này có phù hợp QCVN 40 không",
        input_result={"file_info": {"file_name": "sample.docx"}, "file_content": "COD 120"},
        uploaded_now=True,
        active_document=None,
        active_file_id="",
        active_file_name="",
        active_file_source="",
        active_file_reused=False,
        last_file_chunk_ids=[],
        recent_messages=[],
        title="",
        category="general",
        user_id="user-1",
        kb_version="kb-v1",
        top_k=3,
        prepare_runtime_fn=fake_prepare_runtime,
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {"question": kwargs["question"], "context": kwargs["context"]},
            {
                "status": "success",
                "router_output": "FILE_VS_KB",
                "final_output": "| COD | Đạt |",
            },
        ),
        lookup_cached_response_fn=lambda **kwargs: {
            "answer": "| COD | cached |",
            "router_label": "FILE_VS_KB",
            "cache_key": "cache-key-1",
        },
    )

    assert prepare_calls
    assert workflow_calls
    assert result["comfyui_result"].get("cached") is not True
    assert result["comfyui_result"]["final_output"] == "| COD | Đạt |"
    assert result["text_with_file_cache_key"] == ""


def test_text_with_file_vs_kb_enriches_workflow_question_for_kb_retrieval():
    workflow_calls = []

    def fake_prepare_runtime(**kwargs):
        return {
            "status": "success",
            "file_id": "document-1",
            "active_file_name": "TC-001_ho_so_quan_trac.docx",
            "active_file_source": "uploaded_now",
            "text_with_file_mode": text_with_file_service.TEXT_WITH_FILE_MODE_VS_KB,
            "refined_context": (
                "=== FILE UPLOAD ===\n\n"
                "Question: đánh giá hồ sơ này đạt hay chưa đạt\n\n"
                "Relevant Context:\n"
                "[FILE_SOURCE_1] Mã hồ sơ: TC-001. "
                "Quy chuẩn tham chiếu: QCVN 05:2023/BTNMT. "
                "Thông số quan trắc: SO2 | Trung bình 24 giờ | 118 | µg/Nm3."
            ),
            "retrieved_chunks": [
                {
                    "chunk_id": "chunk-1",
                    "content": (
                        "Quy chuẩn tham chiếu: QCVN 05:2023/BTNMT. "
                        "Thông số quan trắc: SO2 | Trung bình 24 giờ | 118 | µg/Nm3."
                    ),
                }
            ],
            "active_document": None,
        }

    result = text_with_file_service.handle_text_with_file_request(
        normalized_question="đánh giá hồ sơ này đạt hay chưa đạt",
        effective_question="đánh giá hồ sơ này đạt hay chưa đạt",
        input_result={"file_info": {"file_name": "TC-001_ho_so_quan_trac.docx"}, "file_content": ""},
        uploaded_now=True,
        active_document=None,
        active_file_id="",
        active_file_name="",
        active_file_source="",
        active_file_reused=False,
        last_file_chunk_ids=[],
        recent_messages=[],
        title="",
        category="general",
        user_id="user-1",
        kb_version="kb-v1",
        top_k=3,
        prepare_runtime_fn=fake_prepare_runtime,
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {"status": "success", "final_output": "OK", "router_output": "FILE_VS_KB"},
        ),
        lookup_cached_response_fn=lambda **kwargs: None,
    )

    workflow_question = workflow_calls[0]["question"]
    assert workflow_question != "đánh giá hồ sơ này đạt hay chưa đạt"
    assert "QCVN 05:2023/BTNMT" in workflow_question
    assert "SO2" in workflow_question
    assert "Trung bình 24 giờ" in workflow_question
    assert "118" in workflow_question
    assert "µg/Nm3" in workflow_question
    assert result["effective_question"] == "đánh giá hồ sơ này đạt hay chưa đạt"
    assert result["workflow_input"]["question"] == workflow_question


def test_text_with_file_vs_kb_enriches_uppercase_mode_for_kb_retrieval():
    workflow_calls = []

    def fake_prepare_runtime(**kwargs):
        return {
            "status": "success",
            "file_id": "document-17",
            "active_file_name": "TC-017_ho_so_quan_trac.docx",
            "active_file_source": "uploaded_now",
            "text_with_file_mode": "FILE_VS_KB",
            "refined_context": (
                "=== FILE UPLOAD ===\n"
                "[FILE_SOURCE_1] Quy chuẩn tham chiếu | QCVN 14:2008/BTNMT\n"
                "[FILE_SOURCE_2] Phạm vi áp dụng | Nguồn tiếp nhận áp dụng cột A.\n"
                "[FILE_SOURCE_3] pH | Mẫu đơn | 4.9 | -"
            ),
            "retrieved_chunks": [],
            "active_document": None,
        }

    result = text_with_file_service.handle_text_with_file_request(
        normalized_question="đánh giá đạt hay chưa đạt",
        effective_question="đánh giá đạt hay chưa đạt",
        input_result={"file_info": {"file_name": "TC-017_ho_so_quan_trac.docx"}, "file_content": ""},
        uploaded_now=True,
        active_document=None,
        active_file_id="",
        active_file_name="",
        active_file_source="",
        active_file_reused=False,
        last_file_chunk_ids=[],
        recent_messages=[],
        title="",
        category="general",
        user_id="user-1",
        kb_version="kb-v1",
        top_k=3,
        prepare_runtime_fn=fake_prepare_runtime,
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {"status": "success", "final_output": "OK", "router_output": "FILE_VS_KB"},
        ),
        lookup_cached_response_fn=lambda **kwargs: None,
    )

    workflow_question = workflow_calls[0]["question"]
    assert workflow_question != "đánh giá đạt hay chưa đạt"
    assert "QCVN 14:2008/BTNMT" in workflow_question
    assert "pH" in workflow_question
    assert "cột A" in workflow_question
    assert "4.9" in workflow_question
    assert result["workflow_input"]["question"] == workflow_question


def test_text_with_file_vs_kb_workflow_prompts_preserve_old_form_and_compare_decisively():
    workflow = json.loads(Path(chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH).read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}

    assert len(workflow["nodes"]) == 35
    assert len(workflow["links"]) == 68

    node7_prompt = nodes[7]["widgets_values"][0]
    for expected in (
        "Định dạng output bắt buộc",
        "**Kết luận**",
        "**Dữ liệu trong file**",
        "**Căn cứ đối chiếu**",
        "**Nhận xét**",
        "giá trị file <= giới hạn là Đạt",
        "Không dùng giới hạn của thông số này cho thông số khác",
        "Marker nguồn phải đúng dạng [SOURCE_n]",
        "ngày hiệu lực",
        "ký hiệu ghi chú",
        "bảng bị dàn dòng do PDF",
    ):
        assert expected in node7_prompt
    assert "Không bắt buộc dùng bảng" in node7_prompt

    node13_prompt = nodes[13]["widgets_values"][0]
    assert "KIỂM TRA VÀ HOÀN THIỆN" in node13_prompt
    assert "Không dùng giới hạn của thông số đầu tiên cho thông số khác" in node13_prompt
    assert "Bắt buộc trả đúng bốn mục và đúng thứ tự" in node13_prompt
    assert "=== FILE_CONTENT ===" in node13_prompt
    assert "không được nói là thiếu file_content" in node13_prompt

    for node_id in (31, 39):
        prompt = nodes[node_id]["widgets_values"][0]
        assert "đúng bốn mục" in prompt
        assert "không đổi" in prompt.lower()
        assert "kết luận" in prompt.lower()
        assert "[SOURCE_n]" in prompt
        assert "[FILE_SOURCE_n]" in prompt


def test_text_with_file_production_prompts_do_not_hardcode_qcvn_specific_rules():
    workflow = json.loads(Path(chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH).read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in workflow["nodes"]}
    backend_root = Path(__file__).resolve().parents[1]
    production_text = "\n".join(
        [
            (backend_root / "app/services/text_with_file/assessment.py").read_text(encoding="utf-8"),
            (backend_root / "app/services/chat_runtime/workflow_recovery.py").read_text(encoding="utf-8"),
            (backend_root / "app/services/chat_runtime/answer_policy.py").read_text(encoding="utf-8"),
            nodes[7]["widgets_values"][0],
            nodes[13]["widgets_values"][0],
            nodes[31]["widgets_values"][0],
            nodes[39]["widgets_values"][0],
        ]
    )

    forbidden_fragments = (
        "QCVN 05:2023/BTNMT Bảng 1",
        "QCVN 08:2023/BTNMT: Bảng 2",
        "QCVN 08:2023/BTNMT cho sông",
        "PM2,5 trong QCVN 05:2023/BTNMT",
        "45(*)",
        "01/01/2026",
        "_build_targeted_kb_hints",
        "_qcvn08_table_hint",
        "_standard_contains",
    )
    for fragment in forbidden_fragments:
        assert fragment not in production_text

    node31_prompt = nodes[31]["widgets_values"][0]
    assert "=== FILE_CONTENT ===" in node31_prompt
    assert "không được nói là thiếu file_content" in node31_prompt


def test_text_with_file_cache_policy_rejects_unusable_answers():
    assert chat_service._should_cache_text_with_file_answer(
        "| COD | Đạt |",
        "FILE_VS_KB",
    )
    assert not chat_service._should_cache_text_with_file_answer(
        "None",
        "FILE_VS_KB",
    )
    assert not chat_service._should_cache_text_with_file_answer(
        "Error code: 503 - high demand",
        "FILE_VS_KB",
    )
    assert not chat_service._should_cache_text_with_file_answer(
        "| COD | Đạt |",
        "",
    )


def test_sanitize_final_response_still_validates_compacted_raw_router_output():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output="PHAP_LY",
        final_answer="\n  PHAP_LY  \n",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == chat_service.TEXT_ONLY_INVALID_OUTPUT_FALLBACK
    assert router_label == ""
    assert chunks == []


def test_sanitize_text_only_keeps_usable_answer_when_router_runtime_error():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output="error': {'code': 500, 'message': 'Internal error encountered.'}",
        final_answer="Hiện nay, quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT.",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == "Hiện nay, quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT."
    assert router_label == ""
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_text_only_recovers_unique_label_from_dirty_router_output():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output=(
            "Intent: quy chuẩn kỹ thuật quốc gia về tiếng ồn. "
            "</thought>FINAL_LABEL=PHAP_LY"
        ),
        final_answer="QCVN 26:2010/BTNMT là quy chuẩn kỹ thuật quốc gia về tiếng ồn.",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == "QCVN 26:2010/BTNMT là quy chuẩn kỹ thuật quốc gia về tiếng ồn."
    assert router_label == "PHAP_LY"
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_sanitize_text_only_keeps_usable_answer_when_dirty_router_is_unrecoverable():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output=(
            "Intent: hỏi quy chuẩn kỹ thuật quốc gia về tiếng ồn. "
            "Các nhãn gồm PHAP_LY, THONG_SO, QUY_TRINH, HO_SO, VAN_HANH."
        ),
        final_answer="Hiện nay, quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT.",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == "Hiện nay, quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT."
    assert router_label == ""
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_finalize_does_not_treat_dirty_router_label_list_as_greeting():
    answer, chunks = chat_service._finalize_comfyui_response(
        router_output=(
            "Intent: hỏi quy chuẩn kỹ thuật quốc gia.\n"
            "Nhãn hợp lệ: PHAP_LY, THONG_SO, QUY_TRINH, HO_SO, "
            "VAN_HANH, XA_GIAO, KHONG_LIEN_QUAN."
        ),
        raw_answer="QCVN 05:2023/BTNMT là quy chuẩn kỹ thuật quốc gia về chất lượng không khí.",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == "QCVN 05:2023/BTNMT là quy chuẩn kỹ thuật quốc gia về chất lượng không khí."
    assert answer != chat_service.GREETING_ANSWER
    assert chunks == [{"chunk_id": "chunk-1"}]


def test_finalize_still_handles_exact_greeting_router_label():
    answer, chunks = chat_service._finalize_comfyui_response(
        router_output="XA_GIAO",
        raw_answer="raw model answer",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == chat_service.GREETING_ANSWER
    assert chunks == []


def test_sanitize_text_only_falls_back_when_router_and_answer_are_runtime_errors():
    answer, router_label, chunks = chat_service._sanitize_final_response(
        input_type="text_only",
        router_output="error': {'code': 500, 'message': 'Internal error encountered.'}",
        final_answer="Error code: 500 - Internal error encountered.",
        retrieved_chunks=[{"chunk_id": "chunk-1"}],
    )

    assert answer == chat_service.TEXT_ONLY_INVALID_OUTPUT_FALLBACK
    assert router_label == ""
    assert chunks == []








def test_text_only_cache_hit_returns_mongo_answer(monkeypatch):


    user_messages = []


    assistant_messages = []


    cache_queries = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "COD là gì?",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(


        chat_service,


        "find_cached_answer",


        lambda *args, **kwargs: cache_queries.append(kwargs) or {


            "answer": "- COD là nhu cầu oxy hóa học.\n- Đơn vị thường dùng là mg/L.",


            "router_label": "THONG_SO",


            "cache_key": "cod là gì",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("Cache hit must not call ComfyUI")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("Cache hit must not query Chroma")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("Cache hit must not rewrite exact cache")


        ),


    )





    result = chat_service.process_chat_request("COD là gì?")





    assert result["status"] == "success"


    assert result["cached"] is True


    assert result["input_type"] == "text_only"


    assert result["workflow_input"] == {


        "question": "COD là gì?",


        "context": "",


        "follow_up_state": "",


        "question_source_index": 1,


    }


    assert result["comfyui_result"]["final_output"] == (
        "- COD là nhu cầu oxy hóa học.\n- Đơn vị thường dùng là mg/L."
    )


    assert cache_queries == [


        {"kb_version": "v3_structured_policy:router_label_v8_source_format"}


    ]


    assert len(user_messages) == 1


    assert user_messages[0]["workflow_context"] == "[CACHE HIT]"


    assert len(assistant_messages) == 1


    assert assistant_messages[0]["answer"] == (
        "- COD là nhu cầu oxy hóa học.\n- Đơn vị thường dùng là mg/L."
    )


def test_text_only_exact_cache_hit_does_not_call_semantic_lookup():
    state = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="COD là gì?",
        normalized_question="COD là gì?",
        recent_messages=[],
        topic_state={},
        text_only_cache_kb_version="kb-v1",
        run_workflow_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("workflow called")),
        find_cached_answer_fn=lambda *args, **kwargs: {
            "answer": "COD là nhu cầu oxy hóa học.",
            "router_label": "THONG_SO",
            "cache_key": "cod là gì",
        },
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
        lookup_semantic_cached_answer_fn=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("semantic lookup called")
        ),
    )

    assert state["status"] == "cached"
    assert state["response"]["cache_type"] == "exact"
    assert state["response"]["comfyui_result"]["final_output"] == "COD là nhu cầu oxy hóa học."


def test_text_only_semantic_cache_hit_skips_workflow():
    user_messages = []
    assistant_messages = []
    semantic_calls = []

    state = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="tôi muốn biết COD",
        normalized_question="tôi muốn biết COD",
        recent_messages=[],
        topic_state={},
        text_only_cache_kb_version="kb-v1",
        run_workflow_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("workflow called")),
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",
        lookup_semantic_cached_answer_fn=lambda **kwargs: semantic_calls.append(kwargs) or {
            "answer": "COD là nhu cầu oxy hóa học.",
            "router_label": "THONG_SO",
            "cache_key": "cod là gì",
        },
    )

    assert state["status"] == "cached"
    assert state["response"]["cache_type"] == "semantic"
    assert state["response"]["cached"] is True
    assert semantic_calls[0]["kb_version"] == "kb-v1"
    assert user_messages[0]["workflow_context"] == "[SEMANTIC CACHE HIT]"
    assert assistant_messages[0]["workflow_context"] == "[SEMANTIC CACHE HIT]"


def test_text_only_without_cache_calls_comfyui_directly(monkeypatch):


    comfy_calls = []


    user_messages = []


    assistant_messages = []


    cache_writes = []
    semantic_writes = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "COD là gì?",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not query Chroma")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not refine retrieval context")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cod là gì",


    )


    monkeypatch.setattr(


        chat_service,


        "upsert_semantic_answer_cache",


        lambda **kwargs: semantic_writes.append(kwargs),


    )





    def fake_run_comfyui_workflow(**kwargs):


        comfy_calls.append(kwargs)


        return {


            "status": "success",


            "final_output": "COD là nhu cầu oxy hóa học.",


            "router_output": "THONG_SO",


        }





    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_run_comfyui_workflow)





    result = chat_service.process_chat_request("COD là gì?")





    assert result["status"] == "success"


    assert result["input_type"] == "text_only"


    assert result["retrieved_count"] == 0


    assert result["retrieved_chunks"] == []


    assert result["workflow_input"] == {


        "question": "COD là gì?",


        "context": "",


        "follow_up_state": "",


        "question_source_index": 1,


    }


    assert comfy_calls == [
        {
            "question": "COD là gì?",
            "context": "",
            "question_source_index": 1,
        }
    ]
    assert user_messages[0]["workflow_context"] == ""


    assert assistant_messages[0]["workflow_context"] == ""


    assert cache_writes == [


        {


            "question": "COD là gì?",


            "normalized_question": "COD là gì?",


            "answer": "COD là nhu cầu oxy hóa học.",


            "router_label": "THONG_SO",


                "kb_version": "v3_structured_policy:router_label_v8_source_format",


            "source_type": "text_only",


        }


    ]
    assert semantic_writes == [
        {
            "cache_key": "cod là gì",
            "question": "COD là gì?",
            "router_label": "THONG_SO",
            "kb_version": "v3_structured_policy:router_label_v8_source_format",
        }
    ]








def test_text_only_strong_legal_query_forces_router_label(monkeypatch):


    comfy_calls = []


    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_only",
            "normalized_question": "tôi muốn biết QUY CHUẨN KỸ THUẬT QUỐC GIA VỀ TIẾNG ỒN?",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")
    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")
    monkeypatch.setattr(
        chat_service,
        "run_comfyui_workflow",
        lambda **kwargs: comfy_calls.append(kwargs) or {
            "status": "success",
            "final_output": "[PHAP_LY] QCVN 26:2010/BTNMT là quy chuẩn kỹ thuật quốc gia về tiếng ồn.",
            "router_output": "",
        },
    )

    result = chat_service.process_chat_request("tôi muốn biết QUY CHUẨN KỸ THUẬT QUỐC GIA VỀ TIẾNG ỒN?")

    assert comfy_calls == [
        {
            "question": "tôi muốn biết QUY CHUẨN KỸ THUẬT QUỐC GIA VỀ TIẾNG ỒN?",
            "context": "",
            "question_source_index": 1,
        }
    ]
    assert result["router_output"] == ""


def test_text_only_without_cache_applies_greeting_override_before_store(monkeypatch):


    assistant_messages = []


    cache_writes = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "Xin chào",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not query Chroma")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not refine retrieval context")


        ),


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "Xin chào từ LLM",


            "router_output": "XA_GIAO",


        },


    )





    result = chat_service.process_chat_request("Xin chào")





    assert result["retrieved_chunks"] == []


    assert result["retrieved_count"] == 0


    assert result["comfyui_result"]["final_output"] == chat_service.GREETING_ANSWER


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": chat_service.GREETING_ANSWER,


            "workflow_context": "",


            "retrieved_chunk_ids": [],


            "router_label": "XA_GIAO",


        }


    ]


    assert cache_writes == [


        {


            "question": "Xin chào",


            "normalized_question": "Xin chào",


            "answer": chat_service.GREETING_ANSWER,


            "router_label": "XA_GIAO",


            "kb_version": "v3_structured_policy:router_label_v8_source_format",


            "source_type": "text_only",


        }


    ]








def test_text_only_normalizes_router_label_before_assistant_store_and_cache(monkeypatch):


    user_messages = []


    assistant_messages = []


    cache_writes = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "Xin chào",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not query Chroma")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not refine retrieval context")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "Xin chào từ LLM",


            "router_output": "  XA_GIAO\n",


        },


    )





    result = chat_service.process_chat_request("Xin chào")





    assert "router_label" not in user_messages[0]


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": chat_service.GREETING_ANSWER,


            "workflow_context": "",


            "retrieved_chunk_ids": [],


            "router_label": "XA_GIAO",


        }


    ]


    assert cache_writes == [


        {


            "question": "Xin chào",


            "normalized_question": "Xin chào",


            "answer": chat_service.GREETING_ANSWER,


            "router_label": "XA_GIAO",


            "kb_version": "v3_structured_policy:router_label_v8_source_format",


            "source_type": "text_only",


        }


    ]


    assert result["router_output"] == "XA_GIAO"


    assert result["comfyui_result"]["router_output"] == "XA_GIAO"








def test_text_only_without_cache_applies_unrelated_override_before_store(monkeypatch):


    assistant_messages = []


    cache_writes = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "Thời tiết hôm nay thế nào?",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not query Chroma")


        ),


    )


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("text_only must not refine retrieval context")


        ),


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "Raw unrelated answer",


            "router_output": "KHONG_LIEN_QUAN",


        },


    )





    result = chat_service.process_chat_request("Thời tiết hôm nay thế nào?")





    assert result["retrieved_chunks"] == []


    assert result["retrieved_count"] == 0


    assert result["comfyui_result"]["final_output"] == chat_service.UNRELATED_ANSWER


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": chat_service.UNRELATED_ANSWER,


            "workflow_context": "",


            "retrieved_chunk_ids": [],


            "router_label": "KHONG_LIEN_QUAN",


        }


    ]


    assert cache_writes == [


        {


            "question": "Thời tiết hôm nay thế nào?",


            "normalized_question": "Thời tiết hôm nay thế nào?",


            "answer": chat_service.UNRELATED_ANSWER,


            "router_label": "KHONG_LIEN_QUAN",


            "kb_version": "v3_structured_policy:router_label_v8_source_format",


            "source_type": "text_only",


        }


    ]








def test_text_only_does_not_cache_fallback_answer(monkeypatch):


    cache_writes = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "quy trình xữ lý mẫu là gì?",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "Chưa đủ căn cứ từ dử liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",


            "router_output": "QUY_TRINH",


        },


    )





    result = chat_service.process_chat_request("quy trình xữ lý mẫu là gì?")





    assert result["comfyui_result"]["final_output"] == (


        "Chưa đủ căn cứ từ dử liệu gốc được cung cấp để trả lời chính xác câu hỏi này."


    )


    assert cache_writes == []








def test_text_only_does_not_cache_invalid_router_label_output(monkeypatch):


    cache_writes = []


    assistant_messages = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "cụ thể hơn phần 5",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "KHONG_L",


            "router_output": "KHONG_L",


        },


    )





    result = chat_service.process_chat_request("cụ thể hơn phần 5")





    assert result["router_output"] == ""


    assert result["comfyui_result"]["router_output"] == ""


    assert result["comfyui_result"]["final_output"] == chat_service.TEXT_ONLY_INVALID_OUTPUT_FALLBACK


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": chat_service.TEXT_ONLY_INVALID_OUTPUT_FALLBACK,


            "workflow_context": "",


            "retrieved_chunk_ids": [],


            "router_label": "",


        }


    ]


    assert cache_writes == []








def test_text_only_keeps_usable_answer_when_router_runtime_error(monkeypatch):
    cache_writes = []
    assistant_messages = []

    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_only",
            "normalized_question": "tôi muốn biết quy chuẩn quốc gia về kỹ thuật tiếng ồn",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(
        chat_service,
        "add_assistant_message",
        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",
    )
    monkeypatch.setattr(
        chat_service,
        "store_cached_answer",
        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",
    )
    monkeypatch.setattr(
        chat_service,
        "run_comfyui_workflow",
        lambda **kwargs: {
            "status": "success",
            "final_output": "Hiện nay, quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT.",
            "router_output": "error': {'code': 500, 'message': 'Internal error encountered.'}",
        },
    )

    result = chat_service.process_chat_request(
        "tôi muốn biết quy chuẩn quốc gia về kỹ thuật tiếng ồn"
    )

    assert result["router_output"] == ""
    assert (
        result["comfyui_result"]["final_output"]
        == "Hiện nay, quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT."
    )
    assert assistant_messages[0]["answer"] == result["comfyui_result"]["final_output"]
    assert assistant_messages[0]["router_label"] == ""
    assert cache_writes == []


def test_text_only_retries_once_when_router_and_answer_are_runtime_errors(monkeypatch):
    workflow_calls = []

    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_only",
            "normalized_question": "tôi muốn biết quy chuẩn quốc gia về kỹ thuật tiếng ồn",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")
    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")

    def fake_workflow(**kwargs):
        workflow_calls.append(kwargs)
        if len(workflow_calls) == 1:
            return {
                "status": "success",
                "final_output": "Error code: 500 - Internal error encountered.",
                "router_output": "error': {'code': 500, 'message': 'Internal error encountered.'}",
            }
        return {
            "status": "success",
            "final_output": "QCVN 26:2010/BTNMT là quy chuẩn kỹ thuật quốc gia về tiếng ồn.",
            "router_output": "PHAP_LY",
        }

    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_workflow)

    result = chat_service.process_chat_request(
        "tôi muốn biết quy chuẩn quốc gia về kỹ thuật tiếng ồn"
    )

    assert len(workflow_calls) == 2
    assert result["router_output"] == "PHAP_LY"
    assert result["comfyui_result"]["final_output"].startswith("QCVN 26:2010/BTNMT")


def test_text_with_file_keeps_vector_pipeline(monkeypatch):


    comfy_calls = []


    upsert_calls = []


    query_calls = []


    status_updates = []


    cache_writes = []


    active_state_updates = []





    chunk_documents = [


        {


            "chunk_id": "chunk-1",


            "chunk_index": 1,


            "content": "COD là nhu cầu oxy hóa học.",


            "embedding": [0.1, 0.2],


            "document_id": "document-1",


            "source_file_name": "sample.docx",


            "source_file_extension": ".docx",


            "category": "general",


            "kb_version": "v3_structured_policy",


        }


    ]


    retrieved_chunks = [


        {


            "chunk_id": "chunk-1",


            "chunk_index": 1,


            "content": "COD là nhu cầu oxy hóa học.",


            "source_file_name": "sample.docx",


            "source_file_extension": ".docx",


            "document_id": "document-1",


            "category": "general",


            "kb_version": "v3_structured_policy",


            "similarity_score": 0.95,


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_with_file",


            "normalized_question": "COD là gì?",


            "file_info": {


                "file_name": "sample.docx",


                "file_extension": ".docx",


                "file_path": "sample.docx",


                "file_size_bytes": 100,


            },


            "file_content": "COD là nhu cầu oxy hóa học.",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "",


            "active_file_name": "",


            "active_file_mode": "",


            "last_file_effective_question": "",


            "last_file_chunk_ids": [],


            "active_file_updated_at": None,


        },


    )


    monkeypatch.setattr(chat_service, "create_document", lambda **kwargs: "document-1")


    monkeypatch.setattr(


        chat_service,


        "chunk_file_content",


        lambda **kwargs: {


            "status": "success",


            "chunks": [


                {


                    "chunk_id": "chunk-1",


                    "chunk_index": 1,


                    "content": "COD là nhu cầu oxy hóa học.",


                    "source_file_name": "sample.docx",


                    "source_file_extension": ".docx",


                }


            ],


        },


    )


    monkeypatch.setattr(


        chat_service,


        "embed_chunks",


        lambda chunks: {


            "status": "success",


            "chunks": [


                {


                    "chunk_id": "chunk-1",


                    "chunk_index": 1,


                    "content": "COD là nhu cầu oxy hóa học.",


                    "embedding": [0.1, 0.2],


                    "source_file_name": "sample.docx",


                    "source_file_extension": ".docx",


                }


            ],


        },


    )


    monkeypatch.setattr(


        chat_service,


        "build_chunk_documents_for_storage",


        lambda **kwargs: chunk_documents,


    )


    monkeypatch.setattr(chat_service, "save_document_chunks", lambda **kwargs: 1)


    monkeypatch.setattr(


        chat_service,


        "upsert_chunk_embeddings",


        lambda chunks: upsert_calls.append(chunks) or 1,


    )





    def fake_query_similar_chunks_by_question(**kwargs):


        query_calls.append(kwargs)


        return retrieved_chunks





    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        fake_query_similar_chunks_by_question,


    )


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: COD là gì?\n\nFile Context:\n[FILE_SOURCE_1] ...",


            "chunks": retrieved_chunks,


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_document_status",


        lambda document_id, status, kb_version=None: status_updates.append(


            {


                "document_id": document_id,


                "status": status,


                "kb_version": kb_version,


            }


        ),


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    def fake_run_comfyui_workflow(**kwargs):


        comfy_calls.append(kwargs)


        return {


            "status": "success",


            "final_output": "COD là nhu cầu oxy hóa học.",


            "router_output": "THONG_SO",


        }





    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_run_comfyui_workflow)





    result = chat_service.process_chat_request("COD là gì?", file_path="sample.docx")





    assert result["status"] == "success"


    assert result["input_type"] == "text_with_file"


    assert result["document_id"] == "document-1"


    assert result["active_file_id"] == "document-1"


    assert result["active_file_name"] == "sample.docx"


    assert result["active_file_mode"] == chat_service.TEXT_WITH_FILE_MODE_QA


    assert result["active_file_source"] == "uploaded_now"


    assert result["active_file_reused"] is False


    assert len(upsert_calls) == 1


    assert query_calls == [


        {


            "question": "COD là gì?",


            "top_k": 8,


            "where": {"document_id": "document-1"},


        }


    ]


    assert comfy_calls[0]["question"] == "COD là gì?"


    assert "Question: COD là gì?\n\nFile Context:\n[FILE_SOURCE_1] ..." in comfy_calls[0]["context"]


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert "Active File Name: sample.docx" not in comfy_calls[0]["context"]


    assert status_updates == [


        {


            "document_id": "document-1",


            "status": "processed",


            "kb_version": "v3_structured_policy",


        }


    ]


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-1",


            "active_file_name": "sample.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "COD là gì?",


            "last_file_chunk_ids": ["chunk-1"],


            "last_file_anchor_text": ANY,


        }


    ]


    assert cache_writes == []








def test_text_with_file_upload_uses_original_filename_for_storage(monkeypatch):


    create_document_calls = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_with_file",


            "normalized_question": "COD là gì?",


            "file_info": {


                "file_name": "8f0_safe_A.pdf",


                "file_extension": ".pdf",


                "file_path": "D:/uploads/8f0_safe_A.pdf",


                "file_size_bytes": 100,


            },


            "file_content": "COD là nhu cầu oxy hóa học.",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "create_document",


        lambda **kwargs: create_document_calls.append(kwargs) or "document-1",


    )


    monkeypatch.setattr(


        chat_service,


        "chunk_file_content",


        lambda **kwargs: {"status": "success", "chunks": []},


    )


    monkeypatch.setattr(


        chat_service,


        "embed_chunks",


        lambda chunks: {"status": "success", "chunks": []},


    )


    monkeypatch.setattr(chat_service, "build_chunk_documents_for_storage", lambda **kwargs: [])


    monkeypatch.setattr(chat_service, "save_document_chunks", lambda **kwargs: 0)


    monkeypatch.setattr(chat_service, "upsert_chunk_embeddings", lambda chunks: 0)


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: [])


    monkeypatch.setattr(chat_service, "update_document_status", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "COD là nhu cầu oxy hóa học.",


            "router_output": "FILE_QA",


        },


    )





    chat_service.process_chat_request(


        "COD là gì?",


        file_path="D:/uploads/8f0_safe_A.pdf",


        original_filename="A.pdf",


    )





    assert create_document_calls[0]["file_info"]["file_name"] == "A.pdf"


    assert create_document_calls[0]["file_info"]["original_file_name"] == "A.pdf"


    assert create_document_calls[0]["file_info"]["file_path"] == "D:/uploads/8f0_safe_A.pdf"








def test_classify_text_with_file_mode():


    assert (


        chat_service._classify_text_with_file_mode("đây là tài liệu gì?")


        == chat_service.TEXT_WITH_FILE_MODE_QA


    )


    assert (


        chat_service._classify_text_with_file_mode("file này là gì?")


        == chat_service.TEXT_WITH_FILE_MODE_QA


    )


    assert (


        chat_service._classify_text_with_file_mode("tóm tắt file này")


        == chat_service.TEXT_WITH_FILE_MODE_SUMMARY


    )


    assert (


        chat_service._classify_text_with_file_mode("file này nói gì về tiếng ồn")


        == chat_service.TEXT_WITH_FILE_MODE_QA


    )


    assert (


        chat_service._classify_text_with_file_mode("file này có phù hợp QCVN 26 không")


        == chat_service.TEXT_WITH_FILE_MODE_VS_KB


    )


    assert (


        chat_service._classify_text_with_file_mode(
            "Dựa trên file tôi vừa upload, hãy đánh giá hồ sơ quan trắc này đạt hay chưa đạt theo quy chuẩn áp dụng."
        )


        == chat_service.TEXT_WITH_FILE_MODE_VS_KB


    )








def test_build_file_summary_context_uses_file_sources_and_preserves_heading_chunks():


    chunks = [


        {


            "chunk_id": "chunk-1",


            "chunk_index": 1,


            "content": "GIá»šI THIá»†U\nTài liệu này mô tả phạm vi áp dụng.",


            "source_file_name": "sample.docx",


        },


        {


            "chunk_id": "chunk-2",


            "chunk_index": 2,


            "content": "Nội dung chi tiết phần 1.",


            "source_file_name": "sample.docx",


        },


        {


            "chunk_id": "chunk-3",


            "chunk_index": 3,


            "content": "Mục 2\nNội dung chi tiết phần 2.",


            "source_file_name": "sample.docx",


        },


    ]





    context, selected_chunks = chat_service._build_file_summary_context(


        question="tóm tắt tài liệu này",


        chunks=chunks,


        max_context_chars=1000,


    )





    assert "Question: tóm tắt tài liệu này" in context


    assert "File Content:" in context


    assert context.count("[FILE_SOURCE_") == 3


    assert [chunk["chunk_id"] for chunk in selected_chunks] == ["chunk-1", "chunk-3", "chunk-2"]








def test_resolve_file_qa_top_k_expands_for_follow_up_or_long_question():


    assert chat_service._resolve_file_qa_top_k("COD là gì?", 3) == 8


    assert chat_service._resolve_file_qa_top_k("còn chỉ tiêu COD trong tài liệu này thì sao", 3) == 10


    assert (


        chat_service._resolve_file_qa_top_k(


            "trong tài liệu này có nhắc đến yêu cầu lưu ý về thời gian lấy mẫu, cách bảo quản và kết quả phân tích hay không",


            3,


        )


        == 10


    )








def test_text_with_file_summary_uses_broad_context_and_workflow_path(monkeypatch):


    comfy_calls = []





    chunk_documents = [


        {


            "chunk_id": "chunk-1",


            "chunk_index": 1,


            "content": "Mục 1 của tài liệu.",


            "embedding": [0.1, 0.2],


            "document_id": "document-1",


            "source_file_name": "sample.docx",


            "source_file_extension": ".docx",


            "category": "general",


            "kb_version": "v3_structured_policy",


        },


        {


            "chunk_id": "chunk-2",


            "chunk_index": 2,


            "content": "Mục 2 của tài liệu.",


            "embedding": [0.3, 0.4],


            "document_id": "document-1",


            "source_file_name": "sample.docx",


            "source_file_extension": ".docx",


            "category": "general",


            "kb_version": "v3_structured_policy",


        },


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_with_file",


            "normalized_question": "tóm tắt file này",


            "file_info": {


                "file_name": "sample.docx",


                "file_extension": ".docx",


                "file_path": "sample.docx",


                "file_size_bytes": 100,


            },


            "file_content": "Mục 1 của tài liệu.\n\nMục 2 của tài liệu.",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(chat_service, "create_document", lambda **kwargs: "document-1")


    monkeypatch.setattr(


        chat_service,


        "chunk_file_content",


        lambda **kwargs: {"status": "success", "chunks": chunk_documents},


    )


    monkeypatch.setattr(


        chat_service,


        "embed_chunks",


        lambda chunks: {"status": "success", "chunks": chunk_documents},


    )


    monkeypatch.setattr(


        chat_service,


        "build_chunk_documents_for_storage",


        lambda **kwargs: chunk_documents,


    )


    monkeypatch.setattr(chat_service, "save_document_chunks", lambda **kwargs: 2)


    monkeypatch.setattr(chat_service, "upsert_chunk_embeddings", lambda chunks: 2)


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(


            AssertionError("file_summary must not use top-k retrieval")


        ),


    )


    monkeypatch.setattr(chat_service, "update_document_status", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Tóm tắt file.",


            "router_output": "FILE_SUMMARY",


        },


    )





    result = chat_service.process_chat_request("tóm tắt file này", file_path="sample.docx")





    assert result["input_type"] == "text_with_file"


    assert result["workflow_input"]["context"].count("[FILE_SOURCE_") == 2


    assert comfy_calls[0]["question"] == "tóm tắt file này"


    assert result["workflow_input"]["context"] == comfy_calls[0]["context"]


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert "Active File Name: sample.docx" not in comfy_calls[0]["context"]








def test_text_with_file_vs_kb_prefixes_file_context_and_uses_workflow_path(monkeypatch):


    comfy_calls = []


    retrieved_chunks = [


        {


            "chunk_id": "chunk-1",


            "chunk_index": 1,


            "content": "Nội dung file về tiếng ồn.",


            "source_file_name": "sample.docx",


            "source_file_extension": ".docx",


            "document_id": "document-1",


            "category": "general",


            "kb_version": "v3_structured_policy",


            "similarity_score": 0.95,


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_with_file",


            "normalized_question": "file này có phù hợp QCVN 26 không",


            "file_info": {


                "file_name": "sample.docx",


                "file_extension": ".docx",


                "file_path": "sample.docx",


                "file_size_bytes": 100,


            },


            "file_content": "Nội dung file về tiếng ồn.",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(chat_service, "create_document", lambda **kwargs: "document-1")


    monkeypatch.setattr(


        chat_service,


        "chunk_file_content",


        lambda **kwargs: {


            "status": "success",


            "chunks": [


                {


                    "chunk_id": "chunk-1",


                    "chunk_index": 1,


                    "content": "Nội dung file về tiếng ồn.",


                    "source_file_name": "sample.docx",


                    "source_file_extension": ".docx",


                }


            ],


        },


    )


    monkeypatch.setattr(


        chat_service,


        "embed_chunks",


        lambda chunks: {


            "status": "success",


            "chunks": [


                {


                    "chunk_id": "chunk-1",


                    "chunk_index": 1,


                    "content": "Nội dung file về tiếng ồn.",


                    "embedding": [0.1, 0.2],


                    "source_file_name": "sample.docx",


                    "source_file_extension": ".docx",


                }


            ],


        },


    )


    monkeypatch.setattr(


        chat_service,


        "build_chunk_documents_for_storage",


        lambda **kwargs: [


            {


                "chunk_id": "chunk-1",


                "chunk_index": 1,


                "content": "Nội dung file về tiếng ồn.",


                "embedding": [0.1, 0.2],


                "document_id": "document-1",


                "source_file_name": "sample.docx",


                "source_file_extension": ".docx",


                "category": "general",


                "kb_version": "v3_structured_policy:router_label_v2",


            }


        ],


    )


    monkeypatch.setattr(chat_service, "save_document_chunks", lambda **kwargs: 1)


    monkeypatch.setattr(chat_service, "upsert_chunk_embeddings", lambda chunks: 1)


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: retrieved_chunks)


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: file này có phù hợp QCVN 26 không\n\nFile Context:\n[FILE_SOURCE_1] ...",


            "chunks": retrieved_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "update_document_status", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Theo file upload...",


            "router_output": "FILE_VS_KB",


        },


    )





    result = chat_service.process_chat_request(


        "file này có phù hợp QCVN 26 không",


        file_path="sample.docx",


    )





    assert result["workflow_input"]["context"].startswith("=== FILE UPLOAD ===")


    assert comfy_calls[0]["question"] != "file này có phù hợp QCVN 26 không"
    assert "Câu hỏi gốc: file này có phù hợp QCVN 26 không" in comfy_calls[0]["question"]
    assert "QCVN 26" in comfy_calls[0]["question"]
    assert "giới hạn" in comfy_calls[0]["question"]


    assert result["workflow_input"]["context"] == comfy_calls[0]["context"]


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert "Active File Name: sample.docx" not in comfy_calls[0]["context"]


def test_text_with_file_retries_once_when_workflow_node_has_runtime_error(monkeypatch):
    workflow_calls = []
    assistant_messages = []

    request_state = {
        "status": "success",
        "input_type": "text_with_file",
        "effective_question": "file này có phù hợp QCVN 40 không",
        "rewrite_applied": False,
        "rewrite_reason": "",
        "refined_context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 210",
        "retrieved_chunks": [{"chunk_id": "chunk-1"}],
        "workflow_input": {
            "question": "file này có phù hợp QCVN 40 không",
            "context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 210",
            "follow_up_state": "",
            "question_source_index": 1,
        },
        "comfyui_result": {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "Chưa tìm thấy căn cứ phù hợp trong file được cung cấp để trả lời câu hỏi này.",
            "history": {
                "outputs": {
                    "7": {
                        "text": [
                            "Error code: 503 - model is currently experiencing high demand."
                        ]
                    }
                }
            },
        },
        "file_id": "",
        "active_file_id": "",
        "active_file_name": "sample.docx",
        "active_file_mode": "FILE_VS_KB",
        "active_file_source": "uploaded_now",
        "active_file_reused": False,
    }

    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_with_file",
            "normalized_question": "file này có phù hợp QCVN 40 không",
            "file_info": {"file_name": "sample.docx"},
            "file_content": "COD 210",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "get_conversation_topic_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "get_conversation_active_file_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "_handle_text_with_file_request", lambda **kwargs: request_state)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(
        chat_service,
        "add_assistant_message",
        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",
    )

    def fake_workflow(**kwargs):
        workflow_calls.append(kwargs)
        return {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "| Chỉ tiêu | Giá trị trong file | Giới hạn chuẩn | Kết luận |\n| --- | --- | --- | --- |\n| COD | 210 | 150 | Không đạt |",
            "history": {"outputs": {}},
        }

    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_workflow)

    result = chat_service.process_chat_request(
        "file này có phù hợp QCVN 40 không",
        file_path="sample.docx",
    )

    assert len(workflow_calls) == 1
    assert workflow_calls[0]["question"] == request_state["workflow_input"]["question"]
    assert workflow_calls[0]["context"] == request_state["workflow_input"]["context"]
    assert workflow_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH
    assert "| COD | 210 | 150 | Không đạt |" in result["comfyui_result"]["final_output"]
    assert result["router_output"] == "FILE_VS_KB"
    assert assistant_messages[0]["answer"] == result["comfyui_result"]["final_output"]


def test_text_with_file_retry_recovers_valid_preview_when_final_output_errors(monkeypatch):
    workflow_calls = []
    assistant_messages = []

    request_state = {
        "status": "success",
        "input_type": "text_with_file",
        "effective_question": "file này có phù hợp QCVN 40 không",
        "rewrite_applied": False,
        "rewrite_reason": "",
        "refined_context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 210",
        "retrieved_chunks": [{"chunk_id": "chunk-1"}],
        "workflow_input": {
            "question": "file này có phù hợp QCVN 40 không",
            "context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 210",
            "follow_up_state": "",
            "question_source_index": 1,
        },
        "comfyui_result": {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "Chưa tìm thấy căn cứ phù hợp trong file được cung cấp để trả lời câu hỏi này.",
            "history": {"outputs": {"7": {"text": ["Error code: 503 - high demand."]}}},
        },
        "file_id": "",
        "active_file_id": "",
        "active_file_name": "sample.docx",
        "active_file_mode": "FILE_VS_KB",
        "active_file_source": "uploaded_now",
        "active_file_reused": False,
    }

    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_with_file",
            "normalized_question": "file này có phù hợp QCVN 40 không",
            "file_info": {"file_name": "sample.docx"},
            "file_content": "COD 210",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "get_conversation_topic_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "get_conversation_active_file_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "_handle_text_with_file_request", lambda **kwargs: request_state)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(
        chat_service,
        "add_assistant_message",
        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",
    )

    preview_answer = (
        "| Chỉ tiêu | Giá trị trong file | Giới hạn chuẩn | Kết luận |\n"
        "| --- | --- | --- | --- |\n"
        "| COD | 210 | 150 | Không đạt |"
    )

    def fake_workflow(**kwargs):
        workflow_calls.append(kwargs)
        return {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "Error code: 500 - Internal error encountered.",
            "history": {
                "outputs": {
                    "33": {"text": [preview_answer]},
                    "39": {"text": ["Error code: 500 - Internal error encountered."]},
                }
            },
        }

    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_workflow)

    result = chat_service.process_chat_request(
        "file này có phù hợp QCVN 40 không",
        file_path="sample.docx",
    )

    assert len(workflow_calls) == 1
    assert "| COD | 210 | 150 | Không đạt |" in result["comfyui_result"]["final_output"]
    assert "Error code" not in result["comfyui_result"]["final_output"]
    assert assistant_messages[0]["answer"] == result["comfyui_result"]["final_output"]


def test_text_with_file_recovers_specialist_preview_when_downstream_node_errors(monkeypatch):
    workflow_calls = []
    assistant_messages = []

    request_state = {
        "status": "success",
        "input_type": "text_with_file",
        "effective_question": "file này có phù hợp QCVN 40 không",
        "rewrite_applied": False,
        "rewrite_reason": "",
        "refined_context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 120",
        "retrieved_chunks": [{"chunk_id": "chunk-1"}],
        "workflow_input": {
            "question": "file này có phù hợp QCVN 40 không",
            "context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 120",
            "follow_up_state": "",
            "question_source_index": 1,
        },
        "comfyui_result": {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "Chưa tìm thấy căn cứ phù hợp trong file được cung cấp để trả lời câu hỏi này.",
            "history": {"outputs": {"31": {"text": ["Error code: 503 - high demand."]}}},
        },
        "file_id": "",
        "active_file_id": "",
        "active_file_name": "sample.docx",
        "active_file_mode": "FILE_VS_KB",
        "active_file_source": "uploaded_now",
        "active_file_reused": False,
    }

    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_with_file",
            "normalized_question": "file này có phù hợp QCVN 40 không",
            "file_info": {"file_name": "sample.docx"},
            "file_content": "COD 120",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "get_conversation_topic_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "get_conversation_active_file_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "_handle_text_with_file_request", lambda **kwargs: request_state)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(
        chat_service,
        "add_assistant_message",
        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",
    )

    specialist_answer = (
        "**Kết luận**\n"
        "| Chỉ tiêu | Giá trị trong file | Giới hạn chuẩn | Kết luận |\n"
        "| --- | --- | --- | --- |\n"
        "| COD | 120 | 150 | Đạt |"
    )

    def fake_workflow(**kwargs):
        workflow_calls.append(kwargs)
        return {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "Chưa tìm thấy căn cứ phù hợp trong file được cung cấp để trả lời câu hỏi này.",
            "history": {
                "outputs": {
                    "18": {"text": [specialist_answer]},
                    "32": {"text": ["Error code: 503 - high demand."]},
                }
            },
        }

    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_workflow)

    result = chat_service.process_chat_request(
        "file này có phù hợp QCVN 40 không",
        file_path="sample.docx",
    )

    assert len(workflow_calls) == 1
    assert "| COD | 120 | 150 | Đạt |" in result["comfyui_result"]["final_output"]
    assert "Error code" not in result["comfyui_result"]["final_output"]
    assert assistant_messages[0]["answer"] == result["comfyui_result"]["final_output"]


def test_text_with_file_does_not_retry_when_answer_is_usable(monkeypatch):
    request_state = {
        "status": "success",
        "input_type": "text_with_file",
        "effective_question": "file này có phù hợp QCVN 40 không",
        "rewrite_applied": False,
        "rewrite_reason": "",
        "refined_context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 120",
        "retrieved_chunks": [{"chunk_id": "chunk-1"}],
        "workflow_input": {
            "question": "file này có phù hợp QCVN 40 không",
            "context": "=== FILE UPLOAD ===\n[FILE_SOURCE_1] COD 120",
            "follow_up_state": "",
            "question_source_index": 1,
        },
        "comfyui_result": {
            "status": "success",
            "router_output": "FILE_VS_KB",
            "final_output": "| Chỉ tiêu | Kết luận |\n| --- | --- |\n| COD | Đạt |",
            "history": {
                "outputs": {
                    "7": {"text": ["Error code: 503 - transient backup error."]}
                }
            },
        },
        "file_id": "",
        "active_file_id": "",
        "active_file_name": "sample.docx",
        "active_file_mode": "FILE_VS_KB",
        "active_file_source": "uploaded_now",
        "active_file_reused": False,
    }

    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)
    monkeypatch.setattr(
        chat_service,
        "prepare_chatbot_input",
        lambda question, file_path=None: {
            "status": "success",
            "input_type": "text_with_file",
            "normalized_question": "file này có phù hợp QCVN 40 không",
            "file_info": {"file_name": "sample.docx"},
            "file_content": "COD 120",
        },
    )
    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])
    monkeypatch.setattr(chat_service, "get_conversation_topic_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "get_conversation_active_file_state", lambda conversation_id: {})
    monkeypatch.setattr(chat_service, "_handle_text_with_file_request", lambda **kwargs: request_state)
    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")
    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")
    monkeypatch.setattr(
        chat_service,
        "run_comfyui_workflow",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("usable answer must not retry")),
    )

    result = chat_service.process_chat_request(
        "file này có phù hợp QCVN 40 không",
        file_path="sample.docx",
    )

    assert result["comfyui_result"]["final_output"] == "| Chỉ tiêu | Kết luận |\n| --- | --- |\n| COD | Đạt |"
    assert result["router_output"] == "FILE_VS_KB"








def test_text_with_file_unrelated_response_clears_sources_before_return(monkeypatch):


    assistant_messages = []


    cache_writes = []





    retrieved_chunks = [


        {


            "chunk_id": "chunk-1",


            "chunk_index": 1,


            "content": "Nội dung không liên quan.",


            "source_file_name": "sample.docx",


            "source_file_extension": ".docx",


            "document_id": "document-1",


            "category": "general",


            "kb_version": "v3_structured_policy",


            "similarity_score": 0.95,


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_with_file",


            "normalized_question": "Phân tích file này giúp tôi",


            "file_info": {


                "file_name": "sample.docx",


                "file_extension": ".docx",


                "file_path": "sample.docx",


                "file_size_bytes": 100,


            },


            "file_content": "Nội dung file mẫu",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(chat_service, "create_document", lambda **kwargs: "document-1")


    monkeypatch.setattr(


        chat_service,


        "chunk_file_content",


        lambda **kwargs: {


            "status": "success",


            "chunks": [


                {


                    "chunk_id": "chunk-1",


                    "chunk_index": 1,


                    "content": "Nội dung file mẫu",


                    "source_file_name": "sample.docx",


                    "source_file_extension": ".docx",


                }


            ],


        },


    )


    monkeypatch.setattr(


        chat_service,


        "embed_chunks",


        lambda chunks: {


            "status": "success",


            "chunks": [


                {


                    "chunk_id": "chunk-1",


                    "chunk_index": 1,


                    "content": "Nội dung file mẫu",


                    "embedding": [0.1, 0.2],


                    "source_file_name": "sample.docx",


                    "source_file_extension": ".docx",


                }


            ],


        },


    )


    monkeypatch.setattr(


        chat_service,


        "build_chunk_documents_for_storage",


        lambda **kwargs: [


            {


                "chunk_id": "chunk-1",


                "chunk_index": 1,


                "content": "Nội dung file mẫu",


                "embedding": [0.1, 0.2],


                "document_id": "document-1",


                "source_file_name": "sample.docx",


                "source_file_extension": ".docx",


                "category": "general",


                "kb_version": "v3_structured_policy:router_label_v2",


            }


        ],


    )


    monkeypatch.setattr(chat_service, "save_document_chunks", lambda **kwargs: 1)


    monkeypatch.setattr(chat_service, "upsert_chunk_embeddings", lambda chunks: 1)


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: retrieved_chunks,


    )


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: Phân tích file này giúp tôi\n\nFile Context:\n[FILE_SOURCE_1] ...",


            "chunks": retrieved_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "update_document_status", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "Raw unrelated answer",


            "router_output": "KHONG_LIEN_QUAN",


        },


    )





    result = chat_service.process_chat_request(


        "Phân tích file này giúp tôi",


        file_path="sample.docx",


    )





    assert result["retrieved_chunks"] == []


    assert result["retrieved_count"] == 0


    assert result["comfyui_result"]["final_output"] == chat_service.UNRELATED_ANSWER


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": chat_service.UNRELATED_ANSWER,


                "workflow_context": "Question: Phân tích file này giúp tôi\n\nFile Context:\n[FILE_SOURCE_1] ...",


            "retrieved_chunk_ids": [],


            "router_label": "KHONG_LIEN_QUAN",


        }


    ]


    assert cache_writes == []








def test_is_follow_up_question_detects_ambiguous_reference():


    topic_state = {


        "active_topic_id": "PHAP_LY",


        "last_topic_anchor": "Điều 96",


        "last_topic_focus": "yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


        "last_topic_effective_question": "Điều 96 quy định gì?",


        "topic_history_buffer": [],


    }


    assert chat_service._is_follow_up_question("còn khoản 4 thì sao", topic_state=topic_state) is True


    assert (
        chat_service._is_follow_up_question(
            "cho tôi bảng giá trị giới hạn trong không khí xung quanh",
            topic_state={
                "active_topic_id": "PHAP_LY",
                "last_topic_anchor": "QCVN 05:2023/BTNMT, chất lượng không khí",
                "last_topic_focus": "chất lượng không khí xung quanh",
                "last_topic_effective_question": "QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?",
                "topic_history_buffer": [],
            },
        )
        is True
    )

    assert (
        chat_service._is_follow_up_question(
            "quy chuẩn quốc gia về chất lượng không khí",
            topic_state={
                "active_topic_id": "PHAP_LY",
                "last_topic_anchor": "QCVN 26:2010/BTNMT, tiếng ồn",
                "last_topic_focus": "quy chuẩn kỹ thuật quốc gia về tiếng ồn",
                "last_topic_effective_question": "QCVN 26:2010/BTNMT quy định gì về tiếng ồn?",
                "topic_history_buffer": [],
            },
        )
        is False
    )


    assert (


        chat_service._is_follow_up_question(


            "còn về tổ chức thực hiện thì sao",


            topic_state={


                "active_topic_id": "PHAP_LY",


                "last_topic_anchor": "QCVN 26:2010/BTNMT, tiếng ồn",


                "last_topic_focus": "quy chuẩn kỹ thuật quốc gia về tiếng ồn",


                "last_topic_effective_question": "QCVN 26:2010/BTNMT quy định gì về tiếng ồn?",


                "topic_history_buffer": [],


            },


        )


        is False


    )


    assert chat_service._is_follow_up_question("COD là gì?", topic_state=topic_state) is False


    assert chat_service._is_follow_up_question("QCVN 26:2010/BTNMT là gì?", topic_state=topic_state) is False

    assert (
        chat_service._is_follow_up_question(
            "QCVN 26:2010/BTNMT quy định gì?",
            topic_state={
                "active_topic_id": "PHAP_LY",
                "last_topic_anchor": "QCVN 26:2010/BTNMT, tiếng ồn",
                "last_topic_focus": "quy chuẩn kỹ thuật quốc gia về tiếng ồn",
                "last_topic_effective_question": "QCVN 26:2010/BTNMT quy định gì về tiếng ồn?",
                "topic_history_buffer": [],
            },
        )
        is False
    )








def test_build_follow_up_state_uses_latest_anchor_and_history():


    recent_messages = [


        {


            "role": "user",


            "question": "Tôi muốn biết quy chuẩn quốc gia về chất lượng không khí",


            "normalized_question": "Tôi muốn biết quy chuẩn quốc gia về chất lượng không khí",


            "effective_question": "QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?",


        },


        {


            "role": "assistant",


            "answer": "QCVN 05:2023/BTNMT quy định giá trị giới hạn và thông số cơ bản trong không khí xung quanh.",


            "router_label": "PHAP_LY",


        },


    ]





    state = chat_service._build_follow_up_state(


        recent_messages=recent_messages,


        active_file_name="",


        active_file_id="",


    )





    assert "Latest Anchor: QCVN 05:2023/BTNMT" in state


    assert (


        "Latest Effective Question: QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?"


        in state


    )


    assert "Latest Router Label: PHAP_LY" in state


    assert "- User: QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?" in state








def test_text_only_follow_up_table_request_uses_qcvn_anchor_for_workflow(monkeypatch):


    user_messages = []


    comfy_calls = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "cho tôi bảng Giá trị giới hạn tối đa các thông số cơ bản trong không khí xung quanh",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "Tôi muốn biết quy chuẩn quốc gia về chất lượng không khí",


                "normalized_question": "Tôi muốn biết quy chuẩn quốc gia về chất lượng không khí",


                "effective_question": "QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?",


            }


        ],


    )


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Bảng giới hạn tối đa...",


            "router_output": "PHAP_LY",


            "resolved_question": "QCVN 05:2023/BTNMT quy định bảng Giá trị giới hạn tối đa các thông số cơ bản trong không khí xung quanh như thế nào?",


        },


    )





    result = chat_service.process_chat_request(


        "cho tôi bảng Giá trị giới hạn tối đa các thông số cơ bản trong không khí xung quanh"


    )





    assert result["input_type"] == "text_only"


    assert result["query_mode"] == "follow_up"
    assert result["resolution_reason"] == "topic_continuity_overlap"
    assert result["effective_question"].startswith("Ngữ cảnh chủ đề trước:")
    assert "QCVN 05:2023/BTNMT" in result["effective_question"]
    assert (
        "Câu hỏi hiện tại: cho tôi bảng Giá trị giới hạn tối đa các thông số cơ bản trong không khí xung quanh"
        in result["effective_question"]
    )


    assert user_messages[0]["rewrite_applied"] is False


    assert user_messages[0]["rewrite_reason"] == "topic_continuity_overlap"


    assert result["workflow_input"]["question_source_index"] == 1


    assert comfy_calls[0]["question"] == result["effective_question"]


    assert isinstance(comfy_calls[0]["context"], str)


    assert comfy_calls[0]["question_source_index"] == 1


    assert comfy_calls[0]["context"] != ""
    assert "QCVN 05:2023/BTNMT" in comfy_calls[0]["context"]








def test_text_only_follow_up_uses_effective_question_for_cache_and_workflow(monkeypatch):


    user_messages = []


    comfy_calls = []


    cache_writes = []


    cache_lookups = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "còn khoản 4 thì sao",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "Tôi muốn biết Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


                "normalized_question": "Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


                "effective_question": "Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


            }


        ],


    )


    monkeypatch.setattr(


        chat_service,


        "find_cached_answer",


        lambda *args, **kwargs: cache_lookups.append(args[0]) or None,


    )


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Khoản 4 Điều 96 quy định về quan trắc tự động.",


            "router_output": "PHAP_LY",


            "resolved_question": "Khoản 4 Điều 96 quy định gì?",


        },


    )





    result = chat_service.process_chat_request("còn khoản 4 thì sao")





    assert result["query_mode"] == "follow_up"


    assert result["effective_question"].startswith("Ngữ cảnh chủ đề trước:")


    assert "Điều 96" in result["effective_question"]


    assert "Câu hỏi hiện tại: còn khoản 4 thì sao" in result["effective_question"]


    assert result["workflow_input"]["question"] == result["effective_question"]


    assert result["workflow_input"]["question_source_index"] == 1


    assert cache_lookups == [result["effective_question"]]


    assert comfy_calls[0]["question"] == result["effective_question"]


    assert isinstance(comfy_calls[0]["context"], str)


    assert comfy_calls[0]["question_source_index"] == 1


    assert comfy_calls[0]["context"] != ""
    assert "Điều 96" in comfy_calls[0]["context"]


    assert user_messages[0]["effective_question"] == result["effective_question"]


    assert user_messages[0]["rewrite_applied"] is False


    assert user_messages[0]["rewrite_reason"] == "short_question_with_topic_memory"


    assert cache_writes[0]["question"] == result["effective_question"]
    assert cache_writes[0]["router_label"] == "PHAP_LY"








def test_text_only_detail_follow_up_preserves_focus_in_effective_question(monkeypatch):


    comfy_calls = []


    user_messages = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "cụ thể hơn về quy định về thông số quan trắc",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "Nghị định 08/2022/NĐ-CP quy định thế nào về giấy phép môi trường?",


                "normalized_question": "Nghị định 08/2022/NĐ-CP quy định thế nào về giấy phép môi trường?",


                "effective_question": "Nghị định 08/2022/NĐ-CP quy định thế nào về giấy phép môi trường?",


            }


        ],


    )


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: "assistant-msg-1",


    )


    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Nghị định 08/2022/NĐ-CP có quy định về thông số quan trắc.",


            "router_output": "PHAP_LY",


            "resolved_question": "Nghị định 08/2022/NĐ-CP quy định cụ thể thế nào về thông số quan trắc?",


        },


    )





    result = chat_service.process_chat_request("cụ thể hơn về quy định về thông số quan trắc")





    expected_question = "cụ thể hơn về quy định về thông số quan trắc"


    assert result["query_mode"] == "new_topic"


    assert result["effective_question"] == expected_question


    assert result["workflow_input"]["question"] == expected_question


    assert user_messages[0]["effective_question"] == expected_question


    assert user_messages[0]["rewrite_applied"] is False


    assert user_messages[0]["rewrite_reason"] == ""


    assert comfy_calls[0]["question"] == result["effective_question"]


    assert comfy_calls[0]["context"] != ""
    assert "Nghị định 08/2022/NĐ-CP" in comfy_calls[0]["context"]








def test_text_only_new_topic_does_not_rewrite_follow_up(monkeypatch):


    comfy_calls = []


    user_messages = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "COD là gì?",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "get_or_create_conversation",


        lambda **kwargs: "conversation-1",


    )


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "Tôi muốn biết Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


                "normalized_question": "Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


                "effective_question": "Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


            }


        ],


    )


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: "assistant-msg-1",


    )


    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "COD là nhu cầu oxy hóa học.",


            "router_output": "THONG_SO",


        },


    )





    result = chat_service.process_chat_request("COD là gì?")





    assert result["effective_question"] == "COD là gì?"


    assert result["workflow_input"]["question"] == "COD là gì?"


    assert result["workflow_input"]["question_source_index"] == 1


    assert user_messages[0]["rewrite_applied"] is False


    assert user_messages[0]["rewrite_reason"] == ""


    assert comfy_calls[0]["question"] == "COD là gì?"


    assert comfy_calls[0]["question_source_index"] == 1


    assert isinstance(comfy_calls[0]["context"], str)


    assert comfy_calls[0]["context"] != ""
    assert "Use this memory only if it is relevant" in comfy_calls[0]["context"]






def test_text_only_follow_up_retries_no_grounding_with_expanded_context():
    workflow_calls = []

    recent_messages = [
        {
            "role": "user",
            "effective_question": "QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?",
        },
        {
            "role": "assistant",
            "answer": "QCVN 05:2023/BTNMT có bảng giá trị giới hạn tối đa cho các thông số cơ bản.",
            "router_label": "PHAP_LY",
        },
    ]
    topic_state = {
        "active_topic_id": "PHAP_LY",
        "last_topic_anchor": "QCVN 05:2023/BTNMT",
        "last_topic_focus": "bảng giá trị giới hạn tối đa cho các thông số cơ bản",
        "last_topic_effective_question": "QCVN 05:2023/BTNMT quy định gì về chất lượng không khí xung quanh?",
        "topic_history_buffer": [],
    }

    def fake_run_workflow(**kwargs):
        workflow_calls.append(kwargs)
        if len(workflow_calls) == 1:
            return (
                {
                    "question": kwargs["question"],
                    "context": kwargs["context"],
                    "follow_up_state": kwargs["follow_up_state"],
                    "question_source_index": kwargs["question_source_index"],
                },
                {
                    "status": "success",
                    "final_output": "Chưa đủ căn cứ từ dữ liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",
                    "router_output": "PHAP_LY",
                },
            )
        return (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "Phần này được dùng để đối chiếu giá trị đo với giới hạn tối đa.",
                "router_output": "PHAP_LY",
            },
        )

    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="phần này xử lý sao",
        normalized_question="phần này xử lý sao",
        recent_messages=recent_messages,
        topic_state=topic_state,
        text_only_cache_kb_version="v-test",
        run_workflow_fn=fake_run_workflow,
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert len(workflow_calls) == 2
    assert workflow_calls[0]["context"] != ""
    assert workflow_calls[1]["context"] != ""
    assert result["comfyui_result"]["final_output"].startswith("Phần này")


def test_text_only_recovers_grounded_specialist_preview_when_final_fallback():
    workflow_calls = []
    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="tôi muốn biết quy chuẩn kỹ thuật quốc gia về tiếng ồn",
        normalized_question="tôi muốn biết quy chuẩn kỹ thuật quốc gia về tiếng ồn",
        recent_messages=[],
        topic_state={},
        text_only_cache_kb_version="v-test",
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "Chưa đủ căn cứ từ dữ liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",
                "router_output": "PHAP_LY",
                "history": {
                    "outputs": {
                        "30": {
                            "text": [
                                "[PHAP_LY] Quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT [SOURCE_1]."
                            ]
                        }
                    }
                },
            },
        ),
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert len(workflow_calls) == 1
    assert result["query_mode"] == "new_topic"
    assert result["comfyui_result"]["recovered_from_history"] is True
    assert result["comfyui_result"]["final_output"] == (
        "Quy chuẩn kỹ thuật quốc gia về tiếng ồn là QCVN 26:2010/BTNMT [SOURCE_1]."
    )


def test_text_only_new_topic_retries_once_when_source_exists_but_final_fallback():
    workflow_calls = []

    def fake_run_workflow(**kwargs):
        workflow_calls.append(kwargs)
        if len(workflow_calls) == 1:
            return (
                {
                    "question": kwargs["question"],
                    "context": kwargs["context"],
                    "follow_up_state": kwargs["follow_up_state"],
                    "question_source_index": kwargs["question_source_index"],
                },
                {
                    "status": "success",
                    "final_output": "Chưa đủ căn cứ từ dữ liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",
                    "router_output": "PHAP_LY",
                    "history": {
                        "outputs": {
                            "20": {"text": ["[SOURCE_1] QCVN 26:2010/BTNMT về tiếng ồn."]}
                        }
                    },
                },
            )
        return (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "QCVN 26:2010/BTNMT quy định giới hạn tối đa về tiếng ồn [SOURCE_1].",
                "router_output": "PHAP_LY",
            },
        )

    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="tôi muốn biết quy chuẩn kỹ thuật quốc gia về tiếng ồn",
        normalized_question="tôi muốn biết quy chuẩn kỹ thuật quốc gia về tiếng ồn",
        recent_messages=[],
        topic_state={},
        text_only_cache_kb_version="v-test",
        run_workflow_fn=fake_run_workflow,
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert len(workflow_calls) == 2
    assert all(call["question"] == "tôi muốn biết quy chuẩn kỹ thuật quốc gia về tiếng ồn" for call in workflow_calls)
    assert result["comfyui_result"]["final_output"].startswith("QCVN 26:2010/BTNMT")


def test_text_only_does_not_retry_grounding_for_greeting_route():
    workflow_calls = []
    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="xin chào",
        normalized_question="xin chào",
        recent_messages=[],
        topic_state={},
        text_only_cache_kb_version="v-test",
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "Chưa đủ căn cứ từ dữ liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",
                "router_output": "XA_GIAO",
                "history": {
                    "outputs": {
                        "20": {"text": ["[SOURCE_1] Nội dung chuyên môn không nên kích hoạt retry."]}
                    }
                },
            },
        ),
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert len(workflow_calls) == 1
    assert result["comfyui_result"]["final_output"].startswith("Chưa đủ căn cứ")


def test_text_only_follow_up_uses_history_overlap_without_keyword_list():
    workflow_calls = []
    topic_state = {
        "active_topic_id": "PHAP_LY",
        "last_topic_anchor": "QCVN 05:2023/BTNMT",
        "last_topic_focus": "giá trị giới hạn tối đa thông số cơ bản trong không khí xung quanh",
        "last_topic_effective_question": "QCVN 05:2023/BTNMT quy định bảng giá trị giới hạn thế nào?",
        "topic_history_buffer": [],
    }
    recent_messages = [
        {
            "role": "user",
            "effective_question": "QCVN 05:2023/BTNMT quy định bảng giá trị giới hạn thế nào?",
        },
        {
            "role": "assistant",
            "answer": "Bảng này nêu giới hạn tối đa của các thông số cơ bản trong không khí xung quanh.",
            "router_label": "PHAP_LY",
        },
    ]

    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="giá trị giới hạn tối đa ra sao",
        normalized_question="giá trị giới hạn tối đa ra sao",
        recent_messages=recent_messages,
        topic_state=topic_state,
        text_only_cache_kb_version="v-test",
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "Giá trị giới hạn tối đa là căn cứ để đánh giá kết quả quan trắc.",
                "router_output": "PHAP_LY",
            },
        ),
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert result["query_mode"] == "follow_up"
    assert result["resolution_reason"] == "topic_continuity_overlap"
    assert result["effective_question"].startswith("Ngữ cảnh chủ đề trước:")
    assert "QCVN 05:2023/BTNMT" in result["effective_question"]
    assert "Câu hỏi hiện tại: giá trị giới hạn tối đa ra sao" in result["effective_question"]
    assert workflow_calls[0]["question"] == result["effective_question"]
    assert workflow_calls[0]["context"] != ""
    assert "giá trị giới hạn" in workflow_calls[0]["context"]








def test_text_only_short_follow_up_wraps_with_topic_context():
    workflow_calls = []
    cache_lookups = []
    user_messages = []
    topic_state = {
        "active_topic_id": "THONG_SO",
        "last_topic_anchor": "COD",
        "last_topic_focus": "Nhu cầu oxy hóa học",
        "last_topic_effective_question": "COD là gì?",
        "topic_history_buffer": [],
    }
    recent_messages = [
        {"role": "user", "effective_question": "COD là gì?"},
        {"role": "assistant", "answer": "COD có đơn vị mg/L.", "router_label": "THONG_SO"},
    ]

    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="đơn vị",
        normalized_question="đơn vị",
        recent_messages=recent_messages,
        topic_state=topic_state,
        text_only_cache_kb_version="v-test",
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "COD có đơn vị mg/L.",
                "router_output": "THONG_SO",
            },
        ),
        find_cached_answer_fn=lambda *args, **kwargs: cache_lookups.append(args[0]) or None,
        add_user_message_fn=lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert result["query_mode"] == "follow_up"
    assert result["resolution_reason"] == "short_question_with_topic_memory"
    assert result["effective_question"].startswith("Ngữ cảnh chủ đề trước:")
    assert "COD" in result["effective_question"]
    assert "Câu hỏi hiện tại: đơn vị" in result["effective_question"]
    assert workflow_calls[0]["question"] == result["effective_question"]
    assert cache_lookups == [result["effective_question"]]
    assert user_messages == []



def test_text_only_short_question_without_memory_calls_workflow_as_new_topic():
    workflow_calls = []
    result = text_only_service.handle_text_only_request(
        conversation_id="conversation-1",
        question="xin chào",
        normalized_question="xin chào",
        recent_messages=[],
        topic_state={},
        text_only_cache_kb_version="v-test",
        run_workflow_fn=lambda **kwargs: workflow_calls.append(kwargs)
        or (
            {
                "question": kwargs["question"],
                "context": kwargs["context"],
                "follow_up_state": kwargs["follow_up_state"],
                "question_source_index": kwargs["question_source_index"],
            },
            {
                "status": "success",
                "final_output": "Xin chào!",
                "router_output": "XA_GIAO",
            },
        ),
        find_cached_answer_fn=lambda *args, **kwargs: None,
        add_user_message_fn=lambda **kwargs: "user-msg-1",
        add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
    )

    assert result["query_mode"] == "new_topic"
    assert result["effective_question"] == "xin chào"
    assert workflow_calls == [
        {
            "input_type": "text_only",
            "question": "xin chào",
            "context": "",
            "follow_up_state": "",
            "question_source_index": 1,
        }
    ]



def test_text_only_follow_up_cache_key_includes_topic_context():
    calls = []

    def run_case(anchor):
        result = text_only_service.handle_text_only_request(
            conversation_id="conversation-1",
            question="phần 2",
            normalized_question="phần 2",
            recent_messages=[
                {"role": "user", "effective_question": f"{anchor} là gì?"},
                {"role": "assistant", "answer": f"Thông tin về {anchor}.", "router_label": "PHAP_LY"},
            ],
            topic_state={
                "active_topic_id": "PHAP_LY",
                "last_topic_anchor": anchor,
                "last_topic_focus": "",
                "last_topic_effective_question": f"{anchor} là gì?",
                "topic_history_buffer": [],
            },
            text_only_cache_kb_version="v-test",
            run_workflow_fn=lambda **kwargs: (
                {
                    "question": kwargs["question"],
                    "context": kwargs["context"],
                    "follow_up_state": kwargs["follow_up_state"],
                    "question_source_index": kwargs["question_source_index"],
                },
                {"status": "success", "final_output": "OK", "router_output": "PHAP_LY"},
            ),
            find_cached_answer_fn=lambda *args, **kwargs: calls.append(args[0]) or None,
            add_user_message_fn=lambda **kwargs: "user-msg-1",
            add_assistant_message_fn=lambda **kwargs: "assistant-msg-1",
        )
        return result

    first = run_case("QCVN 26:2010/BTNMT")
    second = run_case("QCVN 05:2023/BTNMT")

    assert first["query_mode"] == "follow_up"
    assert second["query_mode"] == "follow_up"
    assert calls[0] != calls[1]
    assert "QCVN 26:2010/BTNMT" in calls[0]
    assert "QCVN 05:2023/BTNMT" in calls[1]


def test_text_with_file_follow_up_reuses_latest_active_file_without_reupload(monkeypatch):


    comfy_calls = []


    user_messages = []


    active_state_updates = []





    document = {


        "_id": "document-a",


        "title": "A.docx",


        "file_name": "A.docx",


        "file_type": ".docx",


        "file_path": "A.docx",


        "file_size_bytes": 128,


        "category": "general",


    }


    stored_chunks = [


        {


            "chunk_id": "chunk-a-1",


            "chunk_index": 1,


            "content": "Tài liệu A nói về quan trắc nước.",


            "source_file_name": "A.docx",


            "source_file_extension": ".docx",


        },


        {


            "chunk_id": "chunk-a-2",


            "chunk_index": 2,


            "content": "Tài liệu A có nội dung về COD.",


            "source_file_name": "A.docx",


            "source_file_extension": ".docx",


        },


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "hãy tóm tắt tài liệu này",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "A.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "tài liệu này là tài liệu gì?",


            "last_file_chunk_ids": ["chunk-a-1"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "list_file_messages",


        lambda conversation_id, limit=50: [{"file_id": "document-a"}],


    )


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: document if document_id == "document-a" else None)


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: stored_chunks if document_id == "document-a" else [],


    )


    monkeypatch.setattr(


        chat_service,


        "create_document",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("follow-up must not create new document")),


    )


    monkeypatch.setattr(


        chat_service,


        "chunk_file_content",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("follow-up must not re-chunk uploaded file")),


    )


    monkeypatch.setattr(


        chat_service,


        "embed_chunks",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("follow-up must not re-embed file")),


    )


    monkeypatch.setattr(


        chat_service,


        "save_document_chunks",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("follow-up must not save chunks again")),


    )


    monkeypatch.setattr(


        chat_service,


        "upsert_chunk_embeddings",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("follow-up must not upsert vectors again")),


    )


    monkeypatch.setattr(


        chat_service,


        "query_similar_chunks_by_question",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("file_summary must not use similarity retrieval")),


    )


    monkeypatch.setattr(


        chat_service,


        "update_document_status",


        lambda **kwargs: (_ for _ in ()).throw(AssertionError("follow-up must not update document status")),


    )


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Tóm tắt tài liệu A.",


            "router_output": "FILE_SUMMARY",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    result = chat_service.process_chat_request("hãy tóm tắt tài liệu này")





    assert result["input_type"] == "text_with_file"


    assert result["document_id"] == "document-a"


    assert result["active_file_id"] == "document-a"


    assert result["active_file_name"] == "A.docx"


    assert result["active_file_mode"] == chat_service.TEXT_WITH_FILE_MODE_SUMMARY


    assert result["active_file_source"] == "active"


    assert result["active_file_reused"] is True


    assert result["workflow_input"]["context"].count("[FILE_SOURCE_") == 2


    assert "ACTIVE_FILE" not in result["workflow_input"]["context"]


    assert result["workflow_input"]["question_source_index"] == 1


    assert user_messages[0]["file_id"] == "document-a"


    assert comfy_calls[0]["question"] == "hãy tóm tắt tài liệu này"


    assert result["workflow_input"]["context"] == comfy_calls[0]["context"]


    assert comfy_calls[0]["question_source_index"] == 1


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert "Active File Name: A.docx" not in comfy_calls[0]["context"]


    assert "Active File Id: document-a" not in comfy_calls[0]["context"]


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-a",


            "active_file_name": "A.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_SUMMARY,


            "last_file_effective_question": "hãy tóm tắt tài liệu này",


            "last_file_chunk_ids": ["chunk-a-1", "chunk-a-2"],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_follow_up_uses_latest_uploaded_file_when_multiple_exist(monkeypatch):


    comfy_calls = []


    active_state_updates = []


    documents = {


        "document-b": {


            "_id": "document-b",


            "title": "B.pdf",


            "file_name": "B.pdf",


            "file_type": ".pdf",


            "file_path": "B.pdf",


            "file_size_bytes": 200,


            "category": "general",


        },


        "document-a": {


            "_id": "document-a",


            "title": "A.docx",


            "file_name": "A.docx",


            "file_type": ".docx",


            "file_path": "A.docx",


            "file_size_bytes": 128,


            "category": "general",


        },


    }


    chunks_by_document = {


        "document-b": [


            {


                "chunk_id": "chunk-b-1",


                "chunk_index": 1,


                "content": "Tài liệu B có nội dung về COD.",


                "source_file_name": "B.pdf",


                "source_file_extension": ".pdf",


            }


        ],


        "document-a": [


            {


                "chunk_id": "chunk-a-1",


                "chunk_index": 1,


                "content": "Tài liệu A nói về tiếng ồn.",


                "source_file_name": "A.docx",


                "source_file_extension": ".docx",


            }


        ],


    }





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "trong tài liệu có nói gì về COD không",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "",


            "active_file_name": "",


            "active_file_mode": "",


            "last_file_effective_question": "",


            "last_file_chunk_ids": [],


            "active_file_updated_at": None,


        },


    )


    monkeypatch.setattr(


        chat_service,


        "list_file_messages",


        lambda conversation_id, limit=50: [{"file_id": "document-b"}, {"file_id": "document-a"}],


    )


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: documents.get(document_id))


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: chunks_by_document.get(document_id, []),


    )


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: [])


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: cụ thể hơn phần 5\n\nFile Context:\n[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "chunks": stored_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Tài liệu B có nói về COD.",


            "router_output": "FILE_QA",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    result = chat_service.process_chat_request("trong tài liệu có nói gì về COD không")





    assert result["input_type"] == "text_with_file"


    assert result["document_id"] == "document-b"


    assert result["active_file_id"] == "document-b"


    assert result["active_file_name"] == "B.pdf"


    assert result["active_file_mode"] == chat_service.TEXT_WITH_FILE_MODE_QA


    assert result["active_file_source"] == "backfilled_latest"


    assert result["active_file_reused"] is True


    assert "Tài liệu B có nội dung về COD." in result["workflow_input"]["context"]


    assert "Tài liệu A nói về tiếng ồn." not in result["workflow_input"]["context"]


    assert comfy_calls[0]["question"] == "trong tài liệu có nói gì về COD không"


    assert result["workflow_input"]["context"] == comfy_calls[0]["context"]


    assert comfy_calls[0]["question_source_index"] == 1


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert "Active File Name: B.pdf" not in comfy_calls[0]["context"]


    assert "Active File Id: document-b" not in comfy_calls[0]["context"]


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-b",


            "active_file_name": "B.pdf",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "trong tài liệu có nói gì về COD không",


            "last_file_chunk_ids": ["chunk-b-1"],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_follow_up_can_switch_active_file_by_name(monkeypatch):


    active_state_updates = []


    documents = {


        "document-b": {


            "_id": "document-b",


            "title": "B.pdf",


            "file_name": "de8c0047c12f_B.pdf",


            "original_file_name": "B.pdf",


            "file_type": ".pdf",


            "file_path": "B.pdf",


            "file_size_bytes": 200,


            "category": "general",


        },


        "document-a": {


            "_id": "document-a",


            "title": "A.pdf",


            "file_name": "296b61b094ce_A.pdf",


            "original_file_name": "A.pdf",


            "file_type": ".pdf",


            "file_path": "A.pdf",


            "file_size_bytes": 128,


            "category": "general",


        },


    }


    chunks_by_document = {


        "document-a": [


            {


                "chunk_id": "chunk-a-1",


                "chunk_index": 1,


                "content": "Tài liệu A có nhắc đến COD.",


                "source_file_name": "A.pdf",


                "source_file_extension": ".pdf",


            }


        ],


        "document-b": [


            {


                "chunk_id": "chunk-b-1",


                "chunk_index": 1,


                "content": "Tài liệu B nói về tiếng ồn.",


                "source_file_name": "B.pdf",


                "source_file_extension": ".pdf",


            }


        ],


    }





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "trong A có nói gì về COD",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-b",


            "active_file_name": "B.pdf",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "trong tài liệu B có gì?",


            "last_file_chunk_ids": ["chunk-b-1"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "list_file_messages",


        lambda conversation_id, limit=50: [{"file_id": "document-b"}, {"file_id": "document-a"}],


    )


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: documents.get(document_id))


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: chunks_by_document.get(document_id, []),


    )


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: [])


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: cụ thể hơn phần 5\n\nFile Context:\n[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "chunks": stored_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "Tài liệu A có nhắc đến COD.",


            "router_output": "FILE_QA",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    result = chat_service.process_chat_request("trong A có nói gì về COD")





    assert result["input_type"] == "text_with_file"


    assert result["document_id"] == "document-a"


    assert result["active_file_id"] == "document-a"


    assert result["active_file_name"] == "A.pdf"


    assert result["active_file_mode"] == chat_service.TEXT_WITH_FILE_MODE_QA


    assert result["active_file_source"] == "matched_by_name"


    assert result["active_file_reused"] is True


    assert "Tài liệu A có nhắc đến COD." in result["workflow_input"]["context"]


    assert "Tài liệu B nói về tiếng ồn." not in result["workflow_input"]["context"]


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-a",


            "active_file_name": "A.pdf",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "trong A có nói gì về COD",


            "last_file_chunk_ids": ["chunk-a-1"],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_short_follow_up_stays_on_active_file(monkeypatch):


    comfy_calls = []


    assistant_messages = []


    active_state_updates = []


    document = {


        "_id": "document-a",


        "title": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "original_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_type": ".docx",


        "file_path": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_size_bytes": 128,


        "category": "general",


    }


    stored_chunks = [


        {


            "chunk_id": "chunk-a-5",


            "chunk_index": 5,


            "content": "Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "source_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "source_file_extension": ".docx",


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "cụ thể hơn phần 5",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_SUMMARY,


            "last_file_effective_question": "tóm tắt nội dung của tài liệu này",


            "last_file_chunk_ids": ["chunk-a-5"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(chat_service, "list_file_messages", lambda conversation_id, limit=50: [{"file_id": "document-a"}])


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: document if document_id == "document-a" else None)


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {"role": "user", "question": "tóm tắt nội dung của tài liệu này", "normalized_question": "tóm tắt nội dung của tài liệu này", "effective_question": "tóm tắt nội dung của tài liệu này"},


            {"role": "assistant", "answer": "Tài liệu nói về quan trắc.", "router_label": "FILE_SUMMARY"},


        ],


    )


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: stored_chunks if document_id == "document-a" else [],


    )


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: [])


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: cụ thể hơn phần 5\n\nFile Context:\n[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "chunks": stored_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Phần 5 nói về ứng dụng kiểm thữ.",


            "router_output": "FILE_QA",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    result = chat_service.process_chat_request("cụ thể hơn phần 5")





    assert result["input_type"] == "text_with_file"


    assert result["active_file_id"] == "document-a"


    assert result["active_file_source"] == "active"


    assert result["active_file_reused"] is True


    assert result["workflow_input"]["question_source_index"] == 1


    assert "Phần 5 nói về ứng dụng kiểm thữ" in result["workflow_input"]["context"]


    assert comfy_calls[0]["question_source_index"] == 1


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert assistant_messages[0]["router_label"] == "FILE_QA"


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "cụ thể hơn phần 5",


            "last_file_chunk_ids": ["chunk-a-5"],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_semantic_follow_up_stays_on_active_file(monkeypatch):


    comfy_calls = []


    assistant_messages = []


    active_state_updates = []


    document = {


        "_id": "document-a",


        "title": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "original_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_type": ".docx",


        "file_path": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_size_bytes": 128,


        "category": "general",


    }


    stored_chunks = [


        {


            "chunk_id": "chunk-a-3",


            "chunk_index": 3,


            "content": (


                "Quy trình xữ lý mẫu và lưu ý nghiệp vụ gồm tiếp nhận thông tin, "


                "chuẩn bị dụng cụ, lấy mẫu, bảo quản, vận chuyển, phân tích và lưu ý "


                "thống nhất mã mẫu, thời gian lấy mẫu, đơn vị đo."


            ),


            "source_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "source_file_extension": ".docx",


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "còn Quy trình xữ lý mẫu và lưu ý nghiệp vụ thì sao",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_SUMMARY,


            "last_file_effective_question": "tóm tắt nội dung của tài liệu này",


            "last_file_chunk_ids": ["chunk-a-3"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(chat_service, "list_file_messages", lambda conversation_id, limit=50: [{"file_id": "document-a"}])


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: document if document_id == "document-a" else None)


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "tóm tắt nội dung của tài liệu này",


                "normalized_question": "tóm tắt nội dung của tài liệu này",


                "effective_question": "tóm tắt nội dung của tài liệu này",


            },


            {


                "role": "assistant",


                "answer": (


                    "Tài liệu liên quan đến quan trắc môi trường nước mặt, có phần "


                    "thông số quan trắc và phần quy trình xữ lý mẫu, lưu ý nghiệp vụ."


                ),


                "router_label": "FILE_SUMMARY",


            },


        ],


    )


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: stored_chunks if document_id == "document-a" else [],


    )


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: stored_chunks)


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": (


                "Question: còn Quy trình xữ lý mẫu và lưu ý nghiệp vụ thì sao\n\n"


                "File Context:\n"


                "[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): "


                "Quy trình xữ lý mẫu và lưu ý nghiệp vụ gồm tiếp nhận thông tin, chuẩn bị dụng cụ, "


                "lấy mẫu, bảo quản, vận chuyển, phân tích và lưu ý thống nhất mã mẫu."


            ),


            "chunks": stored_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Phần quy trình xữ lý mẫu nêu các bước tiếp nhận, lấy mẫu, bảo quản và lưu ý nghiệp vụ.",


            "router_output": "FILE_QA",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    result = chat_service.process_chat_request("còn Quy trình xữ lý mẫu và lưu ý nghiệp vụ thì sao")





    assert result["input_type"] == "text_with_file"


    assert result["active_file_id"] == "document-a"


    assert result["active_file_source"] == "active"


    assert result["active_file_reused"] is True


    assert result["workflow_input"]["question_source_index"] == 1


    assert "Quy trình xữ lý mẫu và lưu ý nghiệp vụ" in result["workflow_input"]["context"]


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert comfy_calls[0]["question_source_index"] == 1


    assert assistant_messages[0]["router_label"] == "FILE_QA"


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "còn Quy trình xữ lý mẫu và lưu ý nghiệp vụ thì sao",


            "last_file_chunk_ids": ["chunk-a-3"],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_retry_rescues_near_threshold_follow_up(monkeypatch):


    comfy_calls = []


    assistant_messages = []


    active_state_updates = []


    cache_writes = []


    document = {


        "_id": "document-a",


        "title": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "original_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_type": ".docx",


        "file_path": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_size_bytes": 128,


        "category": "general",


    }


    stored_chunks = [


        {


            "chunk_id": "chunk-a-3",


            "chunk_index": 3,


            "content": (


                "Quy trình xữ lý mẫu và lưu ý nghiệp vụ gồm tiếp nhận thông tin, "


                "chuẩn bị dụng cụ, lấy mẫu, bảo quản và lưu ý thống nhất mã mẫu."


            ),


            "source_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "source_file_extension": ".docx",


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "nói rõ hơn",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_SUMMARY,


            "last_file_effective_question": "tóm tắt nội dung của tài liệu này",


            "last_file_chunk_ids": ["chunk-a-3"],


            "last_file_anchor_text": (


                "Tài liệu có quy trình xữ lý mẫu và lưu ý nghiệp vụ liên quan đến tiếp nhận "


                "thông tin, lấy mẫu, bảo quản và thống nhất mã mẫu."


            ),


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(chat_service, "list_file_messages", lambda conversation_id, limit=50: [{"file_id": "document-a"}])


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: document if document_id == "document-a" else None)


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "tóm tắt nội dung của tài liệu này",


                "normalized_question": "tóm tắt nội dung của tài liệu này",


                "effective_question": "tóm tắt nội dung của tài liệu này",


            },


            {


                "role": "assistant",


                "answer": "Tài liệu có quy trình xữ lý mẫu và lưu ý nghiệp vụ.",


                "router_label": "FILE_SUMMARY",


            },


        ],


    )


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: stored_chunks if document_id == "document-a" else [],


    )


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: stored_chunks)


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": (


                "Question: nói rõ hơn\n\n"


                "File Context:\n"


                "[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): "


                "Quy trình xữ lý mẫu và lưu ý nghiệp vụ gồm tiếp nhận thông tin, chuẩn bị dụng cụ, "


                "lấy mẫu, bảo quản và lưu ý thống nhất mã mẫu."


            ),


            "chunks": stored_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "store_cached_answer",


        lambda **kwargs: cache_writes.append(kwargs) or "cache-key",


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    def fake_run_comfyui_workflow(**kwargs):


        comfy_calls.append(kwargs)


        if len(comfy_calls) == 1:


            return {


                "status": "success",


                "final_output": "Chưa đủ căn cứ từ dử liệu gốc được cung cấp để trả lời chính xác câu hỏi này.",


                "router_output": "QUY_TRINH",


                "resolved_question": "Quy trình xữ lý mẫu và lưu ý nghiệp vụ có lưu ý gì?",


            }


        return {


            "status": "success",


            "final_output": "Phần lưu ý nghiệp vụ nhấn mạnh việc thống nhất mã mẫu và bảo quản đúng quy trình.",


            "router_output": "FILE_QA",


        }





    monkeypatch.setattr(chat_service, "run_comfyui_workflow", fake_run_comfyui_workflow)





    result = chat_service.process_chat_request("nói rõ hơn")





    assert len(comfy_calls) == 2


    assert comfy_calls[0]["question_source_index"] == 1


    assert comfy_calls[0]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert comfy_calls[1]["workflow_path"] == chat_service.COMFYUI_TEXT_WITH_FILE_WORKFLOW_PATH


    assert comfy_calls[1]["question_source_index"] == 1


    assert result["input_type"] == "text_with_file"


    assert result["active_file_id"] == "document-a"


    assert result["active_file_reused"] is True


    assert result["router_output"] == "FILE_QA"


    assert result["comfyui_result"]["final_output"] == (


        "Phần lưu ý nghiệp vụ nhấn mạnh việc thống nhất mã mẫu và bảo quản đúng quy trình."


    )


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": "Phần lưu ý nghiệp vụ nhấn mạnh việc thống nhất mã mẫu và bảo quản đúng quy trình.",


            "workflow_context": (


                "Question: nói rõ hơn\n\n"


                "File Context:\n"


                "[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): "


                "Quy trình xữ lý mẫu và lưu ý nghiệp vụ gồm tiếp nhận thông tin, chuẩn bị dụng cụ, "


                "lấy mẫu, bảo quản và lưu ý thống nhất mã mẫu."


            ),


            "retrieved_chunk_ids": ["chunk-a-3"],


            "router_label": "FILE_QA",


        }


    ]


    assert cache_writes == []


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "nói rõ hơn",


            "last_file_chunk_ids": ["chunk-a-3"],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_invalid_router_output_falls_back_safely(monkeypatch):


    assistant_messages = []


    active_state_updates = []


    document = {


        "_id": "document-a",


        "title": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "original_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_type": ".docx",


        "file_path": "tai_lieu_mau_quan_trac_moi_truong.docx",


        "file_size_bytes": 128,


        "category": "general",


    }


    stored_chunks = [


        {


            "chunk_id": "chunk-a-5",


            "chunk_index": 5,


            "content": "Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "source_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "source_file_extension": ".docx",


        }


    ]





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "cụ thể hơn phần 5",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_SUMMARY,


            "last_file_effective_question": "tóm tắt nội dung của tài liệu này",


            "last_file_chunk_ids": ["chunk-a-5"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(chat_service, "list_file_messages", lambda conversation_id, limit=50: [{"file_id": "document-a"}])


    monkeypatch.setattr(chat_service, "get_document", lambda document_id: document if document_id == "document-a" else None)


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {"role": "user", "question": "tóm tắt nội dung của tài liệu này", "normalized_question": "tóm tắt nội dung của tài liệu này", "effective_question": "tóm tắt nội dung của tài liệu này"},


            {"role": "assistant", "answer": "Tài liệu nói về quan trắc.", "router_label": "FILE_SUMMARY"},


        ],


    )


    monkeypatch.setattr(


        chat_service,


        "list_document_chunks",


        lambda document_id, kb_version=None: stored_chunks if document_id == "document-a" else [],


    )


    monkeypatch.setattr(chat_service, "query_similar_chunks_by_question", lambda **kwargs: [])


    monkeypatch.setattr(


        chat_service,


        "refine_context",


        lambda **kwargs: {


            "status": "success",


            "refined_context": "Question: cụ thể hơn phần 5\n\nFile Context:\n[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "chunks": stored_chunks,


        },


    )


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(


        chat_service,


        "add_assistant_message",


        lambda **kwargs: assistant_messages.append(kwargs) or "assistant-msg-1",


    )


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: {


            "status": "success",


            "final_output": "KHONG_L",


            "router_output": "KHONG_L",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "update_conversation_active_file_state",


        lambda conversation_id, **kwargs: active_state_updates.append(


            {"conversation_id": conversation_id, **kwargs}


        ),


    )





    result = chat_service.process_chat_request("cụ thể hơn phần 5")





    assert result["input_type"] == "text_with_file"


    assert result["router_output"] == ""


    assert result["comfyui_result"]["router_output"] == ""


    assert result["comfyui_result"]["final_output"] == chat_service.TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK


    assert result["retrieved_chunks"] == []


    assert assistant_messages == [


        {


            "conversation_id": "conversation-1",


            "answer": chat_service.TEXT_WITH_FILE_INVALID_OUTPUT_FALLBACK,


            "workflow_context": "Question: cụ thể hơn phần 5\n\nFile Context:\n[FILE_SOURCE_1] (Nguồn: tai_lieu_mau_quan_trac_moi_truong.docx): Phần 5 nói về ứng dụng kiểm thữ và các câu hỏi mẫu.",


            "retrieved_chunk_ids": [],


            "router_label": "",


        }


    ]


    assert active_state_updates == [


        {


            "conversation_id": "conversation-1",


            "active_file_id": "document-a",


            "active_file_name": "tai_lieu_mau_quan_trac_moi_truong.docx",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "cụ thể hơn phần 5",


            "last_file_chunk_ids": [],


            "last_file_anchor_text": ANY,


        }


    ]








def test_text_with_file_follow_up_without_active_file_stays_text_only(monkeypatch):


    comfy_calls = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "hãy tóm tắt tài liệu này",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "",


            "active_file_name": "",


            "active_file_mode": "",


            "last_file_effective_question": "",


            "last_file_chunk_ids": [],


            "active_file_updated_at": None,


        },


    )


    monkeypatch.setattr(chat_service, "list_file_messages", lambda conversation_id, limit=50: [])


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(chat_service, "add_user_message", lambda **kwargs: "user-msg-1")


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Chưa đủ căn cứ.",


            "router_output": "KHONG_PHU_HOP",


        },


    )





    result = chat_service.process_chat_request("hãy tóm tắt tài liệu này")





    assert result["input_type"] == "text_only"


    assert result["active_file_id"] is None


    assert result["active_file_source"] == ""


    assert result["active_file_reused"] is False


    assert comfy_calls == [{"question": "hãy tóm tắt tài liệu này", "context": "", "question_source_index": 1}]








def test_active_file_does_not_override_new_text_only_topic(monkeypatch):


    comfy_calls = []


    user_messages = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "COD là gì?",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "A.pdf",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "tài liệu này nói gì?",


            "last_file_chunk_ids": ["chunk-a-1"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "list_file_messages",


        lambda conversation_id, limit=50: [{"file_id": "document-a"}],


    )


    monkeypatch.setattr(


        chat_service,


        "get_document",


        lambda document_id: {


            "_id": "document-a",


            "title": "A.pdf",


            "file_name": "uuid_A.pdf",


            "original_file_name": "A.pdf",


            "file_type": ".pdf",


            "file_path": "A.pdf",


            "file_size_bytes": 128,


            "category": "general",


        },


    )


    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *args, **kwargs: [])


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "COD là nhu cầu oxy hóa học.",


            "router_output": "THONG_SO",


        },


    )





    result = chat_service.process_chat_request("COD là gì?")





    assert result["input_type"] == "text_only"


    assert result["active_file_id"] is None


    assert result["active_file_source"] == ""


    assert result["active_file_reused"] is False


    assert user_messages[0]["input_type"] == "text_only"


    assert user_messages[0]["file_id"] is None


    assert comfy_calls == [
        {
            "question": "COD là gì?",
            "context": "",
            "question_source_index": 1,
        }
    ]






def test_text_only_follow_up_ignores_active_file_and_uses_text_history(monkeypatch):


    comfy_calls = []


    user_messages = []





    monkeypatch.setattr(chat_service, "ensure_mongo_indexes", lambda: None)


    monkeypatch.setattr(


        chat_service,


        "prepare_chatbot_input",


        lambda question, file_path=None: {


            "status": "success",


            "input_type": "text_only",


            "normalized_question": "còn khoản 4 thì sao",


        },


    )


    monkeypatch.setattr(chat_service, "get_or_create_conversation", lambda **kwargs: "conversation-1")


    monkeypatch.setattr(


        chat_service,


        "get_conversation_active_file_state",


        lambda conversation_id: {


            "active_file_id": "document-a",


            "active_file_name": "A.pdf",


            "active_file_mode": chat_service.TEXT_WITH_FILE_MODE_QA,


            "last_file_effective_question": "tài liệu này nói gì?",


            "last_file_chunk_ids": ["chunk-a-1"],


            "active_file_updated_at": "2026-04-21T10:00:00+00:00",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "list_file_messages",


        lambda conversation_id, limit=50: [{"file_id": "document-a"}],


    )


    monkeypatch.setattr(


        chat_service,


        "get_document",


        lambda document_id: {


            "_id": "document-a",


            "title": "A.pdf",


            "file_name": "uuid_A.pdf",


            "original_file_name": "A.pdf",


            "file_type": ".pdf",


            "file_path": "A.pdf",


            "file_size_bytes": 128,


            "category": "general",


        },


    )


    monkeypatch.setattr(


        chat_service,


        "list_recent_messages",


        lambda *args, **kwargs: [


            {


                "role": "user",


                "question": "Tôi muốn biết Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


                "normalized_question": "Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


                "effective_question": "Điều 96. Yêu cầu kỹ thuật đối với tổ chức, cá nhân quan trắc môi trường",


            }


        ],


    )


    monkeypatch.setattr(chat_service, "find_cached_answer", lambda *args, **kwargs: None)


    monkeypatch.setattr(


        chat_service,


        "add_user_message",


        lambda **kwargs: user_messages.append(kwargs) or "user-msg-1",


    )


    monkeypatch.setattr(chat_service, "add_assistant_message", lambda **kwargs: "assistant-msg-1")


    monkeypatch.setattr(chat_service, "store_cached_answer", lambda **kwargs: "cache-key")


    monkeypatch.setattr(


        chat_service,


        "run_comfyui_workflow",


        lambda **kwargs: comfy_calls.append(kwargs) or {


            "status": "success",


            "final_output": "Khoản 4 Điều 96 quy định gì.",


            "router_output": "PHAP_LY",


            "resolved_question": "Khoản 4 Điều 96 quy định gì?",


        },


    )





    result = chat_service.process_chat_request("còn khoản 4 thì sao")





    assert result["input_type"] == "text_only"


    assert result["query_mode"] == "follow_up"


    assert result["effective_question"].startswith("Ngữ cảnh chủ đề trước:")


    assert "Điều 96" in result["effective_question"]


    assert "Câu hỏi hiện tại: còn khoản 4 thì sao" in result["effective_question"]


    assert result["active_file_id"] is None


    assert user_messages[0]["input_type"] == "text_only"


    assert user_messages[0]["file_id"] is None


    assert user_messages[0]["rewrite_applied"] is False


    assert user_messages[0]["rewrite_reason"] == "short_question_with_topic_memory"


    assert comfy_calls[0]["question"] == result["effective_question"]


    assert isinstance(comfy_calls[0]["context"], str)


    assert comfy_calls[0]["context"] != ""
    assert "Điều 96" in comfy_calls[0]["context"]









