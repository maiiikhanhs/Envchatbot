from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


pytest.importorskip("langchain_community")
pytest.importorskip("langchain_core")
pytest.importorskip("langchain_text_splitters")


def _load_load_ebd_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "ComfyUI_windows_portable"
        / "ComfyUI"
        / "custom_nodes"
        / "comfyui_LLM_party"
        / "tools"
        / "load_ebd.py"
    )
    spec = importlib.util.spec_from_file_location("codex_load_ebd", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


load_ebd = _load_load_ebd_module()


def _make_doc(source: str, paragraph_index: int, content: str):
    return load_ebd.Document(
        page_content=content,
        metadata={
            "source": source,
            "paragraph_index": str(paragraph_index),
            "subchunk_index": "1",
            "chunk_sequence": str(paragraph_index),
        },
    )


def test_grounded_finalizer_skips_raw_backup_near_duplicate_heading():
    text = """Việc tổ chức thực hiện theo QCVN 26:2010/BTNMT được quy định như sau:

- Văn bản thay thế: Quy chuẩn này áp dụng thay thế cho TCVN 5949:1998.
- Trách nhiệm tuân thủ: Các tổ chức, cá nhân liên quan phải tuân thủ quy chuẩn.

[PHAP_LY] Tổ chức thực hiện theo QCVN 26:2010/BTNMT được quy định như sau:

- Văn bản thay thế: Quy chuẩn này áp dụng thay thế cho TCVN 5949:1998.
- Trách nhiệm tuân thủ: Các tổ chức, cá nhân liên quan phải tuân thủ quy chuẩn.
"""

    answer, has_grounded, debug = load_ebd._build_grounded_final_response(
        text,
        "fallback",
    )

    assert has_grounded is True
    assert answer.count("Tổ chức thực hiện theo QCVN 26:2010/BTNMT") == 0
    assert answer.count("Việc tổ chức thực hiện theo QCVN 26:2010/BTNMT") == 1
    assert "Skipped backup duplicate/near-duplicate block." in debug


def test_grounded_finalizer_uses_raw_backup_when_primary_is_runtime_error():
    text = """Error code: 500 - Internal error encountered.

[PHAP_LY] Tổ chức thực hiện theo QCVN 26:2010/BTNMT được quy định như sau:
- Cơ quan quản lý nhà nước về môi trường có trách nhiệm hướng dẫn, kiểm tra, giám sát.
"""

    answer, has_grounded, debug = load_ebd._build_grounded_final_response(
        text,
        "fallback",
    )

    assert has_grounded is True
    assert "Cơ quan quản lý nhà nước" in answer
    assert "Internal error" not in answer
    assert "Used raw specialist backup because primary was unusable." in debug


def test_grounded_finalizer_deduplicates_raw_backup_after_primary_fallback():
    text = """Chưa đủ căn cứ từ dữ liệu gốc được cung cấp để trả lời chính xác câu hỏi này.

[PHAP_LY]
Phương pháp xác định tiếng ồn theo QCVN 26 được quy định như sau:
- Phương pháp đo tiếng ồn thực hiện theo Bộ TCVN 7878, gồm 2 phần [SOURCE_1].
- TCVN 7878 - 1:2008 Phần 1: Các đại lượng cơ bản và phương pháp đánh giá [SOURCE_1].
- TCVN 7878 - 2:2010 Phần 2: Xác định mức áp suất âm [SOURCE_1].

Phương pháp xác định tiếng ồn theo QCVN 26 được thực hiện như sau:
- Thực hiện theo Bộ TCVN 7878, gồm 2 phần [SOURCE_1].
- TCVN 7878 - 1:2008 Phần 1: Các đại lượng cơ bản và phương pháp đánh giá [SOURCE_1].
- TCVN 7878 - 2:2010 Phần 2: Xác định mức áp suất âm [SOURCE_1].
"""

    answer, has_grounded, debug = load_ebd._build_grounded_final_response(
        text,
        "fallback",
    )

    assert has_grounded is True
    assert answer.count("Bộ TCVN 7878") == 1
    assert "Skipped backup duplicate/near-duplicate block." in debug


def _make_base(docs):
    return SimpleNamespace(
        docstore=SimpleNamespace(_dict={str(index): doc for index, doc in enumerate(docs, start=1)})
    )


def test_classify_query_intent_marks_qcvn_topic_queries():
    assert (
        load_ebd.classify_query_intent("hãy cho tôi biết quy chuẩn kĩ thuật quốc gia về tiếng ồn")
        == load_ebd.QUERY_MODE_QCVN_TOPIC_TARGETED
    )


def test_grounded_finalizer_falls_back_for_runtime_error_only():
    answer, has_grounded_answer, debug = load_ebd._build_grounded_final_response(
        "Error code: 500 - Internal error encountered.",
        "fallback",
    )

    assert answer == "fallback"
    assert has_grounded_answer is False
    assert "Runtime/API error blocks: 1" in debug


def test_grounded_finalizer_keeps_valid_block_after_runtime_error():
    answer, has_grounded_answer, debug = load_ebd._build_grounded_final_response(
        "Error code: 500 - Internal error encountered.\n\n"
        "[PHAP_LY] QCVN 26:2010/BTNMT quy định giới hạn tiếng ồn.",
        "fallback",
    )

    assert answer == "QCVN 26:2010/BTNMT quy định giới hạn tiếng ồn."
    assert has_grounded_answer is True
    assert "Grounded blocks: 1" in debug


def test_grounded_finalizer_removes_nonetype_type_error_line():
    answer, has_grounded_answer, debug = load_ebd._build_grounded_final_response(
        "expected string or bytes-like object, got 'NoneType'\n\n"
        "[PHAP_LY] QCVN 26:2010/BTNMT quy định giới hạn tiếng ồn.",
        "fallback",
    )

    assert answer == "QCVN 26:2010/BTNMT quy định giới hạn tiếng ồn."
    assert has_grounded_answer is True
    assert "Runtime/API error blocks: 1" in debug


def test_grounded_finalizer_strips_thought_and_keeps_final_answer():
    answer, has_grounded_answer, debug = load_ebd._build_grounded_final_response(
        "<thought>internal reasoning</thought>[PHAP_LY] QCVN 05:2023/BTNMT về chất lượng không khí.",
        "fallback",
    )

    assert answer == "QCVN 05:2023/BTNMT về chất lượng không khí."
    assert has_grounded_answer is True
    assert "Grounded blocks: 1" in debug


def test_title_exact_does_not_misclassify_generic_qcvn_noise_query():
    nd08_source = "D:/kb/08_2022_ND-CP_479457.docx"
    grouped_docs = {
        nd08_source: [
            _make_doc(
                nd08_source,
                410,
                "d) Dự án đầu tư có thay đổi làm phát sinh các thông số ô nhiễm vượt quy chuẩn kỹ thuật môi trường về chất thải; tăng mức độ ô nhiễm tiếng ồn, độ rung.",
            )
        ]
    }

    title_match = load_ebd._find_title_exact_match(
        "hãy cho tôi biết quy chuẩn kĩ thuật quốc gia về tiếng ồn",
        grouped_docs,
    )

    assert title_match is None


def test_qcvn_topic_query_prefers_qcvn_source_over_semantic_noise_source():
    nd08_source = "D:/kb/08_2022_ND-CP_479457.docx"
    qcvn26_source = "D:/kb/Quy-chuan-Viet-Nam-QCVN-26-2010-BTNMT.docx"

    nd08_doc = _make_doc(
        nd08_source,
        410,
        "d) Dự án đầu tư có thay đổi làm phát sinh các thông số ô nhiễm vượt quy chuẩn kỹ thuật môi trường về chất thải; tăng mức độ ô nhiễm tiếng ồn, độ rung.",
    )
    qcvn26_docs = [
        _make_doc(
            qcvn26_source,
            1,
            "QCVN 26:2010/BTNMT\nQuy chuẩn kỹ thuật quốc gia về tiếng ồn",
        ),
        _make_doc(
            qcvn26_source,
            2,
            "1. Phạm vi điều chỉnh\nQuy chuẩn này quy định giới hạn tối đa cho phép về tiếng ồn tại khu vực công cộng và khu dân cư.",
        ),
    ]

    base = _make_base([nd08_doc, *qcvn26_docs])
    assembled_docs = load_ebd._assemble_docs_for_question(
        base,
        "hãy cho tôi biết quy chuẩn kĩ thuật quốc gia về tiếng ồn",
        [nd08_doc],
    )

    assert len(assembled_docs) == 1
    assert assembled_docs[0].metadata["source"] == qcvn26_source
    assert assembled_docs[0].metadata["query_mode"] == load_ebd.QUERY_MODE_QCVN_TOPIC_TARGETED
    assert assembled_docs[0].metadata["canonical_reference"] == "QCVN 26:2010/BTNMT"
    assert "QCVN 26:2010/BTNMT" in assembled_docs[0].page_content


def test_title_exact_prefers_matching_legal_document_type():
    law_source = "D:/kb/Luat-Bao-ve-moi-truong-2020.docx"
    decree_source = "D:/kb/08_2022_ND-CP_479457.docx"

    law_docs = [
        _make_doc(
            law_source,
            1,
            "LUẬT BẢO VỆ MÔI TRƯỜNG\nLuật này quy định về bảo vệ môi trường, quyền, nghĩa vụ và trách nhiệm của cơ quan, tổ chức, cộng đồng dân cư, hộ gia đình và cá nhân.",
        ),
        _make_doc(
            law_source,
            2,
            "Điều 1. Phạm vi điều chỉnh\nLuật này quy định hoạt động bảo vệ môi trường.",
        ),
    ]
    decree_docs = [
        _make_doc(
            decree_source,
            1,
            "NGHỊ ĐỊNH 08/2022/NĐ-CP\nQuy định chi tiết một số điều của Luật Bảo vệ môi trường.",
        )
    ]

    grouped_docs = {
        law_source: law_docs,
        decree_source: decree_docs,
    }

    title_match = load_ebd._find_title_exact_match(
        "tôi muốn biết Luật Bảo vệ môi trường",
        grouped_docs,
    )

    assert title_match is not None
    assert title_match["source"] == law_source


def test_title_exact_query_assembles_from_canonical_law_source():
    law_source = "D:/kb/Luat-Bao-ve-moi-truong-2020.docx"
    decree_source = "D:/kb/08_2022_ND-CP_479457.docx"

    law_docs = [
        _make_doc(
            law_source,
            1,
            "LUẬT BẢO VỆ MÔI TRƯỜNG\nLuật này quy định về bảo vệ môi trường, quyền, nghĩa vụ và trách nhiệm của cơ quan, tổ chức, cộng đồng dân cư, hộ gia đình và cá nhân.",
        ),
        _make_doc(
            law_source,
            2,
            "Điều 1. Phạm vi điều chỉnh\nLuật này quy định hoạt động bảo vệ môi trường.",
        ),
    ]
    decree_doc = _make_doc(
        decree_source,
        1,
        "NGHỊ ĐỊNH 08/2022/NĐ-CP\nQuy định chi tiết một số điều của Luật Bảo vệ môi trường.",
    )

    base = _make_base([decree_doc, *law_docs])
    assembled_docs = load_ebd._assemble_docs_for_question(
        base,
        "tôi muốn biết Luật Bảo vệ môi trường",
        [decree_doc],
    )

    assert len(assembled_docs) == 1
    assert assembled_docs[0].metadata["source"] == law_source
    assert assembled_docs[0].metadata["query_mode"] == load_ebd.QUERY_MODE_TITLE_EXACT
    assert "LUẬT BẢO VỆ MÔI TRƯỜNG" in assembled_docs[0].page_content


def test_reference_exact_qcvn_query_prefers_relevant_section_within_resolved_source():
    qcvn14_source = "D:/kb/QCVN-14-2008.pdf"
    docs = [
        _make_doc(
            qcvn14_source,
            1,
            "QCVN 14:2008/BTNMT\nQuy chuẩn kỹ thuật quốc gia về nước thải sinh hoạt",
        ),
        _make_doc(
            qcvn14_source,
            2,
            "1.1. Phạm vi điều chỉnh\nQuy chuẩn này quy định giá trị tối đa cho phép của các thông số ô nhiễm trong nước thải sinh hoạt khi thải ra môi trường.",
        ),
        _make_doc(
            qcvn14_source,
            19,
            "2.3.2. Hệ số Kq ứng với dung tích của nguồn tiếp nhận nước thải là hồ, ao, đầm được quy định tại Bảng 3 dưới đây.",
        ),
        _make_doc(
            qcvn14_source,
            20,
            "Bảng 3: Hệ số Kq ứng với dung tích của nguồn tiếp nhận nước thải\nV ≤ 10 x 10^6: 0,6\n10 x 10^6 < V ≤ 100 x 10^6: 0,8\nV > 100 x 10^6: 1,0",
        ),
    ]

    base = _make_base(docs)
    assembled_docs = load_ebd._assemble_docs_for_question(
        base,
        "QCVN 14:2008/BTNMT quy định gì về giá trị hệ số K của quy chuẩn kĩ thuật quốc gia về nước thải sinh hoạt?",
        [docs[0], docs[1]],
    )

    assert len(assembled_docs) == 1
    assert assembled_docs[0].metadata["source"] == qcvn14_source
    assert assembled_docs[0].metadata["query_mode"] == load_ebd.QUERY_MODE_REFERENCE_EXACT
    assert "Hệ số Kq" in assembled_docs[0].page_content
    assert "Bảng 3" in assembled_docs[0].page_content


def test_file_vs_kb_assessment_query_prefers_quantitative_table_over_principle_text():
    qcvn_source = "D:/kb/QCVN-08-2023-BTNMT.pdf"
    docs = [
        _make_doc(
            qcvn_source,
            1,
            "QCVN 08:2023/BTNMT\nQuy chuẩn kỹ thuật quốc gia về chất lượng nước mặt",
        ),
        _make_doc(
            qcvn_source,
            10,
            "Bảng 2. Giá trị giới hạn các thông số trong nước mặt phục vụ bảo vệ đời sống thủy sinh\n"
            "Thông số | Đơn vị | Mức A | Mức B",
        ),
        _make_doc(
            qcvn_source,
            11,
            "pH | - | 6,0 - 8,5 | 6,0 - 8,5\n"
            "BOD5 | mg/L | ≤ 4 | ≤ 6\n"
            "COD | mg/L | ≤ 10 | ≤ 15\n"
            "DO | mg/L | ≥ 6,0 | ≥ 5,0",
        ),
        _make_doc(
            qcvn_source,
            14,
            "3.1. Nguyên tắc lựa chọn bảng giá trị giới hạn\n"
            "Việc lựa chọn bảng giá trị giới hạn phụ thuộc vào mục đích sử dụng nguồn nước mặt.",
        ),
    ]
    query = (
        "Yêu cầu: đối chiếu FILE UPLOAD với KB để kết luận Đạt/Chưa đạt. "
        "Chuẩn cần tra: QCVN 08:2023/BTNMT. Nhóm dữ liệu cần tra: Nước mặt. "
        "Điều kiện áp dụng: Mức phân loại mục tiêu: B. "
        "Thông số cần tra giới hạn: pH; BOD5; COD; DO. "
        "Tín hiệu tra KB: giá trị giới hạn ngưỡng khoảng giá trị dòng thông số cột mức điều kiện bảng ghi chú hiệu lực."
    )

    assert load_ebd._lexical_score(query, docs[2]) > load_ebd._lexical_score(query, docs[3])

    assembled_docs = load_ebd._assemble_docs_for_question(
        _make_base(docs),
        query,
        [docs[3]],
    )

    assert len(assembled_docs) == 1
    assert "6,0 - 8,5" in assembled_docs[0].page_content
    assert "BOD5" in assembled_docs[0].page_content
    assert "Nguyên tắc lựa chọn" not in assembled_docs[0].page_content


def test_file_vs_kb_assessment_context_hint_preserves_effective_footnote_without_conclusion():
    qcvn_source = "D:/kb/QCVN-05-2023-BTNMT.pdf"
    doc = _make_doc(
        qcvn_source,
        10,
        "Bảng 1. Giá trị giới hạn tối đa các thông số cơ bản trong không khí xung quanh\n"
        "Thông số | Đơn vị | Trung bình 24 giờ | Trung bình năm\n"
        "Bụi PM2,5 | µg/Nm3 | 50 45(*) | 25\n"
        "Ghi chú:\n"
        "- (*): Giá trị nồng độ áp dụng từ ngày 01 tháng 01 năm 2026.",
    )
    query = (
        "Yêu cầu: đối chiếu FILE UPLOAD với KB để kết luận Đạt/Chưa đạt. "
        "Chuẩn cần tra: QCVN 05:2023/BTNMT. "
        "Ngày liên quan trong file: 2026-02-01. "
        "Thông số cần tra giới hạn: Bụi PM2,5. "
        "Tín hiệu tra KB: giá trị giới hạn ngưỡng khoảng cột mức bảng ghi chú hiệu lực."
    )

    serialized = load_ebd._serialize_retrieved_docs([doc], question=query)

    assert "[RETRIEVAL_HINT]" in serialized
    assert "45(*)" in serialized
    assert "01/01/2026" in serialized
    assert "Đạt" not in serialized
    assert "Chưa đạt" not in serialized


def test_outline_query_assembles_heading_list_instead_of_only_opening_scope():
    qcvn14_source = "D:/kb/QCVN-14-2008.pdf"
    docs = [
        _make_doc(
            qcvn14_source,
            1,
            "QCVN 14:2008/BTNMT\nQuy chuẩn kỹ thuật quốc gia về nước thải sinh hoạt",
        ),
        _make_doc(
            qcvn14_source,
            2,
            "1.1. Phạm vi điều chỉnh\nQuy chuẩn này quy định giá trị tối đa cho phép của các thông số ô nhiễm trong nước thải sinh hoạt khi thải ra môi trường.",
        ),
        _make_doc(
            qcvn14_source,
            3,
            "1.2. Đối tượng áp dụng\nQuy chuẩn này áp dụng đối với cơ sở công cộng, doanh trại lực lượng vũ trang, cơ sở dịch vụ, khu chung cư và khu dân cư.",
        ),
        _make_doc(
            qcvn14_source,
            4,
            "1.3. Giải thích thuật ngữ\nNước thải sinh hoạt là nước thải từ các hoạt động sinh hoạt của con người.",
        ),
        _make_doc(
            qcvn14_source,
            5,
            "2. QUY ĐỊNH KỸ THUẬT\nGiá trị Cmax được tính theo công thức.",
        ),
        _make_doc(
            qcvn14_source,
            6,
            "2.1. Giá trị C\nBảng 1 quy định giá trị C của các thông số ô nhiễm.",
        ),
    ]

    base = _make_base(docs)
    assembled_docs = load_ebd._assemble_docs_for_question(
        base,
        "tóm tắt các đầu mục của quy chuẩn kĩ thuật quốc gia về nước thải sinh hoạt",
        [docs[0], docs[1]],
    )

    assert len(assembled_docs) == 1
    assert assembled_docs[0].metadata["source"] == qcvn14_source
    assert assembled_docs[0].metadata["query_mode"] == load_ebd.QUERY_MODE_OUTLINE
    assert "1.1. Phạm vi điều chỉnh" in assembled_docs[0].page_content
    assert "1.2. Đối tượng áp dụng" in assembled_docs[0].page_content
    assert "2. QUY ĐỊNH KỸ THUẬT" in assembled_docs[0].page_content
    assert "2.1. Giá trị C" in assembled_docs[0].page_content
