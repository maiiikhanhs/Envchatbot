from __future__ import annotations

import time


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def log_chat_latency(timings: dict[str, int], **details) -> None:
    detail_text = " ".join(
        f"{key}={value}" for key, value in details.items() if value not in (None, "")
    )
    timing_text = " ".join(f"{key}_ms={value}" for key, value in timings.items())
    print(f"[LATENCY] chat {detail_text} {timing_text}".strip())
