"""Writes sensor readings into InfluxDB time-series bucket."""
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from src.config.settings import settings

_client = InfluxDBClient(url=settings.influxdb_url, token=settings.influxdb_token, org=settings.influxdb_org)
_write_api = _client.write_api(write_options=SYNCHRONOUS)


def write_reading(data: dict):
    point = (
        Point("sensor_reading")
        .tag("factory_id", data["factory_id"])
        .tag("line_id", data["line_id"])
        .tag("machine_id", data["machine_id"])
        .tag("sensor_type", data["sensor_type"])
        .field("value", float(data["value"]))
        .field("unit", data["unit"])
    )
    _write_api.write(bucket=settings.influxdb_bucket, record=point)