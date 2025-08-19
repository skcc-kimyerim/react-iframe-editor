import logging
import logging.config
import os

import yaml
from core.config import get_setting
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import (
    LoggerProvider,
    LoggingHandler,
)
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

settings = get_setting()

_opentelemetry_initialized = False
_otel_provider: LoggerProvider | None = None
_app_logger = None

log_dir = settings.DATA_PATH + settings.LOG_PATH
info_dir = os.path.join(log_dir, "info")
debug_dir = os.path.join(log_dir, "debug")

os.makedirs(info_dir, exist_ok=True)
os.makedirs(debug_dir, exist_ok=True)

# Load the config file
logging_file = os.path.join(os.path.dirname(__file__), "logging_config.yaml")
with open(logging_file, "rt", encoding="utf-8") as f:
    config = yaml.safe_load(f.read())

    pod_name = os.getenv("POD_NAME", "default-pod")

    config["handlers"]["info_file"]["filename"] = os.path.join(
        info_dir, f"{pod_name}.log"
    )
    config["handlers"]["debug_file"]["filename"] = os.path.join(
        debug_dir, f"{pod_name}-debug.log"
    )


class SuppressGrafanaFilter(logging.Filter):
    """Custom filter to filter out Grafana Alloy endpoint debug logs"""

    def filter(self, record: logging.LogRecord) -> bool:
        # "http://grafana-alloy" 엔드포인트 문자열이 포함된 debug 로그만 무시
        if record.levelno == logging.DEBUG:
            if (
                record.name.startswith("urllib3.connectionpool")
                and "http://grafana-alloy" in record.getMessage()
            ):
                return False
        return True


def _initialize_opentelemetry() -> None:
    """Initialize OpenTelemetry logging system (called once at module load time)"""
    global _otel_provider

    # OTEL 로그 시스템 초기화
    _otel_provider = LoggerProvider(
        resource=Resource.create(
            {
                "service.name": "ms-ai-chat",
                "service.instance.id": os.uname().nodename,
            }
        ),
    )
    set_logger_provider(_otel_provider)

    # OTLP Exporter
    otlp_exporter = OTLPLogExporter(
        endpoint="grafana-alloy.grafana-alloy.svc.cluster.local:4317", insecure=True
    )
    _otel_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))


def _initialize_logging() -> None:
    global _opentelemetry_initialized
    global _otel_provider

    logging.config.dictConfig(config)

    # Otel LoggerProvider 중복 설정 WARNING 메시지 제어를 위한 log level 설정
    logging.getLogger("opentelemetry._logs._internal").setLevel(logging.ERROR)

    if settings.ENVIRONMENT != "LOCAL":
        if not _opentelemetry_initialized:
            _initialize_opentelemetry()
            _opentelemetry_initialized = True

        otel_handler = LoggingHandler(
            level=logging.DEBUG, logger_provider=_otel_provider
        )
        logging.getLogger().addHandler(otel_handler)

    for handler in logging.root.handlers:
        if type(handler) is logging.StreamHandler:
            handler.setLevel(settings.LOG_LEVEL)


def get_logging() -> logging.Logger:
    """Get or initialize the application logger"""
    global _app_logger

    if _app_logger:
        return _app_logger

    _initialize_logging()

    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("azure").setLevel(logging.DEBUG)
    logging.getLogger("openai").setLevel(logging.DEBUG)

    logging.getLogger("httpcore").setLevel(logging.INFO)
    logging.getLogger("urllib3.connectionpool").addFilter(SuppressGrafanaFilter())

    # 필요할 때 주석 해제해서 로깅
    # if settings.ENVIRONMENT == "LOCAL":
    #     logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)
    #     logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.DEBUG)
    #     logging.getLogger("sqlalchemy.orm").setLevel(logging.DEBUG)
    #     logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
    #     logging.getLogger("sqlalchemy.orm.session").setLevel(logging.DEBUG)
    #     logging.getLogger("sqlalchemy.orm.loading").setLevel(logging.DEBUG)
    #     logging.getLogger("sqlalchemy.dialects").setLevel(logging.INFO)

    #     # psycopg2/psycopg 드라이버에서 plan cache 오류 캐치
    #     logging.getLogger("psycopg2").setLevel(logging.DEBUG)
    #     logging.getLogger("psycopg").setLevel(logging.DEBUG)

    #     # SQLAlchemy PostgreSQL 방언
    #     logging.getLogger("sqlalchemy.dialects.postgresql").setLevel(logging.DEBUG)

    _app_logger = logging.getLogger(settings.APP_NAME)
    _app_logger.setLevel(logging.DEBUG)

    return _app_logger
