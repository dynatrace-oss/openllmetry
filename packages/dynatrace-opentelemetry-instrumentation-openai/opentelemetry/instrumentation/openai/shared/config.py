from typing import Callable

from dynatrace_ai_logging import DtAiLogging


class Config:
    enrich_token_usage = False
    enrich_assistant = False
    exception_logger = None
    get_common_metrics_attributes: Callable[[], dict] = lambda: {}
    upload_base64_image: Callable[[str, str, str], str] = lambda trace_id, span_id, base64_image_url: str
    event_logger:DtAiLogging = None
    service_name:str = ""