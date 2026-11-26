"""
Prometheus metrics for platform observability — tracks API latency, request
counts, error rates. Separate from factory sensor monitoring (Layer 2).
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

# Custom business metrics beyond default HTTP metrics
ml_prediction_counter = Counter(
    "neuroplant_ml_predictions_total", "Total ML predictions made", ["model_name"]
)
active_alarms_gauge = Gauge(
    "neuroplant_active_alarms", "Current active alarm count", ["severity"]
)
mqtt_messages_counter = Counter(
    "neuroplant_mqtt_messages_total", "Total MQTT messages processed"
)


def instrument_app(app):
    """Call this on your FastAPI app to auto-track request latency/count/errors."""
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    return app


def record_prediction(model_name: str):
    ml_prediction_counter.labels(model_name=model_name).inc()


def update_alarm_gauge(severity: str, count: int):
    active_alarms_gauge.labels(severity=severity).set(count)


def record_mqtt_message():
    mqtt_messages_counter.inc()