"""
PWA push notification service — sends browser push alerts to plant manager
on Critical alarm events. Uses VAPID keys for Web Push protocol.
"""
from pywebpush import webpush, WebPushException
import json
from src.config.settings import settings

# Subscriptions stored in-memory for demo — production would use PostgreSQL table
_subscriptions = []


def generate_vapid_keys():
    """Run once to generate VAPID keypair — paste output into .env"""
    from py_vapid import Vapid
    vapid = Vapid()
    vapid.generate_keys()
    print("Public key:", vapid.public_key)
    print("Private key:", vapid.private_key)


def register_subscription(subscription_info: dict):
    """Called from frontend when user grants push permission."""
    _subscriptions.append(subscription_info)
    print(f"Subscription registered. Total subscribers: {len(_subscriptions)}")


def send_critical_alert(title: str, body: str, machine_id: str = None):
    """Sends push notification to all registered subscribers."""
    payload = json.dumps({
        "title": title,
        "body": body,
        "machine_id": machine_id,
        "icon": "/icons/alert-icon.png",
    })

    sent_count = 0
    for sub in _subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claim_email},
            )
            sent_count += 1
        except WebPushException as e:
            print(f"Push failed for one subscriber: {e}")

    print(f"Alert sent to {sent_count}/{len(_subscriptions)} subscribers")
    return sent_count


if __name__ == "__main__":
    # First run: generate keys and add to .env
    print("Generating VAPID keys (run once, save to .env)...")
    generate_vapid_keys()