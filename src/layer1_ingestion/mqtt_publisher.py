"""Publishes simulated sensor readings to MQTT broker on a loop."""
import time
import json
import paho.mqtt.client as mqtt
from src.config.settings import settings
from src.layer1_ingestion.synthetic_sensor_generator import get_all_readings, load_topology

client = mqtt.Client()


def connect():
    client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, 60)
    client.loop_start()


def publish_loop(fault_machine_id: str | None = None):
    topology = load_topology()
    interval = topology["publish_interval_ms"] / 1000
    print(f"Publishing every {interval}s. Fault injected on: {fault_machine_id or 'none'}")
    while True:
        readings = get_all_readings(fault_machine_id)
        for r in readings:
            topic = f"{r['factory_id']}/{r['line_id']}/{r['machine_id']}/{r['sensor_type']}"
            client.publish(topic, json.dumps(r))
        time.sleep(interval)


if __name__ == "__main__":
    connect()
    # Set fault_machine_id="M01" to simulate a degrading machine
    publish_loop(fault_machine_id=None)