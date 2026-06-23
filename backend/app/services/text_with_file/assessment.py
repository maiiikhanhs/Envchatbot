from __future__ import annotations

from dataclasses import dataclass
import re

from app.services.chat_text_only_service import _compact_text


KNOWN_PARAMETERS = (
    "SO2",
    "NO2",
    "CO",
    "O3",
    "PM2,5",
    "PM10",
    "TSP",
    "LAeq",
    "BOD5",
    "COD",
    "pH",
    "DO",
    "TSS",
    "Amoni",
    "Tổng nitơ",
    "Tổng dầu mỡ khoáng",
    "Chất rắn lơ lửng",
    "Lưu huỳnh đioxit",
)

UNIT_PATTERN = r"(?:µg/Nm3|μg/Nm3|ug/Nm3|mg/Nm3|mg/L|dBA|%)"
NUMBER_PATTERN = r"\d+(?:[.,]\d+)?"
DATE_PATTERN = r"(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})"
TABLE_INTENT_TERMS = (
    "giá trị giới hạn ngưỡng khoảng giá trị dòng thông số cột mức điều kiện bảng "
    "ghi chú hiệu lực áp dụng từ ngày"
)
MEASUREMENT_VERBS_PATTERN = r"(?:giá trị|ghi nhận|kết quả|đo được|quan trắc|nồng độ|mức|chỉ tiêu|thông số)"
CONDITION_LABEL_PATTERN = (
    r"(?:phạm\s*vi\s*áp\s*dụng|nguồn\s*tiếp\s*nhận|loại\s*hình|"
    r"khu\s*vực|khung\s*giờ|thời\s*gian\s*đo|ngày\s*đo|"
    r"thông\s*tin\s*hiệu\s*lực|điều\s*kiện\s*áp\s*dụng)"
)


@dataclass(frozen=True)
class Measurement:
    parameter: str
    value: float
    raw_value: str
    unit: str
    line: str


def _unique_ordered(values: list[str], *, limit: int = 12) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        compact = _compact_text(value)
        if not compact:
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_values.append(compact)
        if len(unique_values) >= limit:
            break
    return unique_values


def _normalize_symbol_text(text: str) -> str:
    normalized = str(text or "")
    replacements = {
        "SO₂": "SO2",
        "NO₂": "NO2",
        "O₃": "O3",
        "PM₂,₅": "PM2,5",
        "μg/Nm3": "µg/Nm3",
        "ug/Nm3": "µg/Nm3",
        "µg/Nm^3": "µg/Nm3",
        "μg/Nm^3": "µg/Nm3",
        "mg/Nm^3": "mg/Nm3",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _number_to_float(value: str) -> float:
    return float(str(value).replace(",", "."))


def _extract_standards(text: str) -> list[str]:
    matches = re.findall(
        r"\bQCVN\s*\d+(?:[-:][A-Z0-9]+)?(?::\d{4})?(?:\s*/\s*BTNMT)?\b",
        text,
        flags=re.IGNORECASE,
    )
    return _unique_ordered([re.sub(r"\s+", " ", match).replace(" /", "/").replace("/ ", "/") for match in matches])


def _extract_parameters(text: str) -> list[str]:
    normalized = _normalize_symbol_text(text)
    found: list[str] = []
    for parameter in KNOWN_PARAMETERS:
        flags = 0 if parameter == "pH" else re.IGNORECASE
        if re.search(rf"(?<!\w){re.escape(parameter)}(?!\w)", normalized, flags=flags):
            found.append(parameter)

    lines = [_compact_text(line) for line in re.split(r"[\r\n]+", normalized)]
    for line in lines:
        found.extend(_extract_parameter_candidates_from_line(line))
    return _unique_ordered(found)


def _extract_parameter_candidates_from_line(line: str) -> list[str]:
    if not line:
        return []

    candidates: list[str] = []
    label_match = re.search(
        r"(?:thông\s*số(?:\s*quan\s*trắc)?|chỉ\s*tiêu)\s*(?:\||:|-)\s*([^|\n\r.;]+)",
        line,
        flags=re.IGNORECASE,
    )
    if label_match:
        candidates.extend(_split_parameter_candidates(label_match.group(1)))

    cells = [_compact_text(cell) for cell in line.split("|")]
    if len(cells) >= 3 and re.search(NUMBER_PATTERN, line) and _line_has_measurement_signal(line):
        candidates.extend(_split_parameter_candidates(cells[0]))

    value_match = re.search(
        rf"([A-Za-zÀ-Ỹà-ỹ0-9,./+\-\s]{{1,60}}?)\s*(?:có|là|=|:)?\s*{NUMBER_PATTERN}\s*(?:{UNIT_PATTERN}|$)",
        line,
        flags=re.IGNORECASE,
    )
    if value_match and _line_has_measurement_signal(line):
        candidates.extend(_split_parameter_candidates(value_match.group(1)))

    return [candidate for candidate in candidates if _is_plausible_parameter(candidate)]


def _split_parameter_candidates(value: str) -> list[str]:
    normalized = _normalize_symbol_text(value)
    pieces = re.split(r"\s*(?:,|;|/|\bvà\b)\s*", normalized, flags=re.IGNORECASE)
    return [_clean_parameter_candidate(piece) for piece in pieces]


def _clean_parameter_candidate(value: str) -> str:
    cleaned = _compact_text(value)
    cleaned = re.sub(r"^(?:mỗi\s+)?(?:thông\s*số|chỉ\s*tiêu)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*(?:có|là|=|:|-)\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\b{NUMBER_PATTERN}\b.*$", "", cleaned).strip(" .:-|")
    return cleaned


def _is_plausible_parameter(value: str) -> bool:
    candidate = _compact_text(value)
    if not candidate or len(candidate) > 60:
        return False
    if not re.search(r"[A-Za-zÀ-Ỹà-ỹ]", candidate):
        return False
    rejected = {
        "mã hồ sơ",
        "quy chuẩn tham chiếu",
        "nhóm dữ liệu",
        "phạm vi áp dụng",
        "đơn vị",
        "mẫu đơn",
        "ngày đo",
        "nguồn tiếp nhận",
        "giá trị",
        "kết quả",
    }
    return candidate.lower() not in rejected


def _line_has_measurement_signal(line: str) -> bool:
    return bool(
        re.search(UNIT_PATTERN, line, flags=re.IGNORECASE)
        or re.search(MEASUREMENT_VERBS_PATTERN, line, flags=re.IGNORECASE)
        or "|" in line
    )


def _extract_conditions(text: str) -> list[str]:
    patterns = (
        (r"(?:Bảng|bảng)\s+\d+(?:[A-Z])?", 0),
        r"Trung bình\s+(?:1|8|24)\s+giờ",
        r"Trung bình\s+năm",
        (r"(?:cột|Cột)\s+[A-Z0-9]+(?![A-Za-zÀ-Ỹà-ỹ])", 0),
        (r"(?:mức|Mức)\s+[A-Z0-9]+(?![A-Za-zÀ-Ỹà-ỹ])", 0),
        r"mức\s+phân\s+loại\s+mục\s+tiêu\s*:\s*[A-Z0-9]+",
        r"khu vực\s+[^\n\r|.;]+",
        r"ban\s+(?:ngày|đêm)",
        r"khung giờ\s+từ\s+\d{1,2}:\d{2}\s+đến\s+\d{1,2}:\d{2}",
        r"\bK[A-Za-z]?\s*=\s*\d+(?:[.,]\d+)?",
        r"(?:ngày\s+đo|thời\s+gian\s+đo)\s*(?:\||:|-)\s*[^\n\r|.;]+",
        rf"{CONDITION_LABEL_PATTERN}\s*(?:\||:|-)\s*[^\n\r|.;]+",
        r"(?:áp\s*dụng|hiệu\s*lực)\s+từ\s+ngày\s+[^\n\r|.;]+",
    )
    found: list[str] = []
    for pattern_item in patterns:
        if isinstance(pattern_item, tuple):
            pattern, flags = pattern_item
        else:
            pattern, flags = pattern_item, re.IGNORECASE
        found.extend(re.findall(pattern, text, flags=flags))
    return _unique_ordered(found)


def _extract_dates(text: str) -> list[str]:
    return _unique_ordered(re.findall(DATE_PATTERN, text), limit=8)


def _extract_data_groups(text: str) -> list[str]:
    patterns = (
        r"Nhóm dữ liệu\s*\|?\s*[:\-]?\s*([^\n\r|.]+)",
        r"Nước thải sinh hoạt",
        r"Nước thải công nghiệp",
        r"Nước mặt",
        r"Không khí xung quanh",
        r"Khí thải",
        r"Tiếng ồn",
    )
    found: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            found.append(match if isinstance(match, str) else " ".join(match))
    return _unique_ordered(found)


def _extract_measurement_lines(text: str, parameters: list[str]) -> list[str]:
    normalized = _normalize_symbol_text(text)
    lines = [
        _compact_text(
            re.sub(
                r"^(?:=+\s*FILE UPLOAD\s*=+\s*)?(?:\[FILE_SOURCE_\d+\]\s*)?",
                "",
                line,
                flags=re.IGNORECASE,
            )
        )
        for line in re.split(r"[\r\n]+", normalized)
        if _compact_text(line)
    ]
    selected: list[str] = []
    for line in lines:
        for parameter in parameters:
            flags = 0 if parameter == "pH" else re.IGNORECASE
            if not re.search(rf"(?<!\w){re.escape(parameter)}(?!\w)", line, flags=flags):
                continue
            if _extract_measurement_value(line, parameter):
                selected.append(line)
                break
    return _unique_ordered(selected, limit=8)


def _extract_measurements(text: str, parameters: list[str]) -> list[Measurement]:
    measurement_lines = _extract_measurement_lines(text, parameters)
    measurements: list[Measurement] = []
    seen: set[tuple[str, str]] = set()

    for line in measurement_lines:
        for parameter in parameters:
            flags = 0 if parameter == "pH" else re.IGNORECASE
            if not re.search(rf"(?<!\w){re.escape(parameter)}(?!\w)", line, flags=flags):
                continue
            raw_value = _extract_measurement_value(line, parameter)
            if not raw_value:
                continue
            try:
                value = _number_to_float(raw_value)
            except ValueError:
                continue
            unit_match = re.search(UNIT_PATTERN, line, flags=re.IGNORECASE)
            unit = unit_match.group(0) if unit_match else ""
            key = (parameter.lower(), raw_value)
            if key in seen:
                continue
            seen.add(key)
            measurements.append(
                Measurement(
                    parameter=parameter,
                    value=value,
                    raw_value=raw_value,
                    unit=unit,
                    line=line,
                )
            )
            break

    return measurements


def _extract_measurement_value(line: str, parameter: str) -> str:
    cells = [_compact_text(cell) for cell in line.split("|")]
    if len(cells) >= 3:
        flags = 0 if parameter == "pH" else re.IGNORECASE
        if not re.search(rf"(?<!\w){re.escape(parameter)}(?!\w)", cells[0], flags=flags):
            return ""
        for cell in reversed(cells):
            if re.fullmatch(NUMBER_PATTERN, cell):
                return cell
    elif "|" in line:
        return ""

    if not re.search(r"(giá trị|ghi nhận|kết quả|đo được)", line, flags=re.IGNORECASE):
        return ""
    cleaned = re.sub(UNIT_PATTERN, "", line, flags=re.IGNORECASE)
    cleaned = re.sub(re.escape(parameter), "", cleaned, flags=re.IGNORECASE)
    numbers = re.findall(NUMBER_PATTERN, cleaned)
    return numbers[-1] if numbers else ""


def _build_assessment_text(
    *,
    original_question: str,
    refined_context: str,
    retrieved_chunks: list[dict] | None,
    include_original_question: bool,
) -> tuple[str, list[str], list[str], list[str], list[str], list[Measurement]]:
    original = _compact_text(original_question)
    file_content = _normalize_symbol_text(refined_context)
    chunk_text = "\n".join(str(chunk.get("content", "")) for chunk in retrieved_chunks or [])
    combined_text = f"{file_content}\n{chunk_text}"

    standards = _extract_standards(combined_text)
    candidate_parameters = _extract_parameters(combined_text)
    conditions = _extract_conditions(combined_text)
    dates = _extract_dates(combined_text)
    data_groups = _extract_data_groups(combined_text)
    measurements = _extract_measurements(combined_text, candidate_parameters)
    parameters = _unique_ordered([measurement.parameter for measurement in measurements])
    if not parameters:
        parameters = candidate_parameters
    measurement_lines = _unique_ordered([measurement.line for measurement in measurements], limit=8)

    parts = [
        "Yêu cầu: đối chiếu FILE UPLOAD với KB để kết luận Đạt/Chưa đạt.",
        f"Câu hỏi gốc: {original}" if include_original_question and original else "",
        f"Chuẩn cần tra: {'; '.join(standards)}." if standards else "",
        f"Nhóm dữ liệu cần tra: {'; '.join(data_groups)}." if data_groups else "",
        f"Điều kiện áp dụng: {'; '.join(conditions)}." if conditions else "",
        f"Ngày liên quan trong file: {'; '.join(dates)}." if dates else "",
        f"Thông số cần tra giới hạn: {'; '.join(parameters)}." if parameters else "",
        f"Dữ liệu đo trong file: {'; '.join(measurement_lines)}." if measurement_lines else "",
        "Nếu KB có nhiều giới hạn cho cùng thông số, phải tra cả ghi chú, hiệu lực và ngày áp dụng để chọn đúng giới hạn theo ngày trong file." if dates else "",
        "Nếu một dòng KB có thêm giá trị kèm ký hiệu ghi chú hiệu lực, giá trị có ghi chú là phiên bản thay thế cho điều kiện liên quan khi ngày trong file đã thỏa ghi chú." if dates else "",
        f"Tín hiệu tra KB: {TABLE_INTENT_TERMS}.",
        "Hãy tìm đúng giới hạn, ngưỡng hoặc khoảng giá trị tương ứng trong KB và so sánh.",
    ]
    return (
        "\n".join(part for part in parts if part).strip(),
        standards,
        parameters,
        conditions,
        data_groups,
        measurements,
    )


def build_file_vs_kb_workflow_question(
    *,
    original_question: str,
    refined_context: str,
    file_content: str = "",
    retrieved_chunks: list[dict] | None = None,
) -> str:
    """Build a KB-retrieval-oriented question for file-vs-KB assessment."""
    original = _compact_text(original_question)
    question, standards, parameters, conditions, data_groups, measurements = _build_assessment_text(
        original_question=original,
        refined_context=f"{file_content}\n{refined_context}",
        retrieved_chunks=retrieved_chunks,
        include_original_question=True,
    )

    if not standards and not parameters and not conditions and not data_groups and not measurements:
        return original

    return question


def build_file_vs_kb_retry_question(
    *,
    original_question: str,
    refined_context: str,
    retrieved_chunks: list[dict] | None = None,
) -> str:
    question, standards, parameters, conditions, data_groups, measurements = _build_assessment_text(
        original_question=original_question,
        refined_context=refined_context,
        retrieved_chunks=retrieved_chunks,
        include_original_question=False,
    )
    if not standards or not parameters or not measurements:
        return ""

    compact_parts = [
        "; ".join(standards),
        "; ".join(data_groups),
        "; ".join(parameters),
        "; ".join(conditions),
        question,
        TABLE_INTENT_TERMS,
    ]
    return _compact_text(" ".join(part for part in compact_parts if part)) or question
