"""Subscribes to all sensor topics, forwards each reading to InfluxDB + Redis cache."""
import json
import paho.mqtt.client as mqtt
from src.config.settings import settings
from src.layer1_ingestion.influxdb_writer import write_reading
import redis

redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def on_connect(client, userdata, flags, rc):
    print(f"Connected with code {rc}")
    client.subscribe("#")  # all topics


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        write_reading(data)
        cache_key = f"{data['factory_id']}:{data['line_id']}:{data['machine_id']}:{data['sensor_type']}"
        redis_client.set(cache_key, json.dumps(data), ex=30)
        if data["value"] >= data["critical_threshold"]:
            print(f"CRITICAL ALARM: {cache_key} = {data['value']}")
        elif data["value"] >= data["warning_threshold"]:
            print(f"WARNING: {cache_key} = {data['value']}")
    except Exception as e:
        print(f"Error processing message: {e}")


def run():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, 60)
    client.loop_forever()


if __name__ == "__main__":
    run()