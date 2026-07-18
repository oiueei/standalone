"""OIUEEI load-test scenarios for Locust.

Run ONLY against a disposable staging target (see stress-testing.md) — never
production. Two user classes mirror the real traffic mix:

- AnonymousVisitor — the open web: public collections, things, /legal, /health.
- AuthenticatedMember — dashboard reads and an occasional write, using
  pre-generated Bearer tokens (OIUEEI's auth is magic-link: there is no
  password to log in with, so tokens are minted out-of-band on the staging
  target and fed here via TOKENS_FILE; each simulated member keeps one token
  for its whole session, like a real browser would).

Usage:
    TOKENS_FILE=tokens.txt PUBLIC_COLLECTION=l1l1C1 \
    locust -f stress_test_locust.py --host https://<staging>.herokuapp.com \
           -u 50 -r 5 --run-time 10m --headless --csv results
"""

import os
import random
from pathlib import Path

from locust import HttpUser, between, task

# A PUBLIC collection code on the staging target (seed_demo provides l1l1C1).
PUBLIC_COLLECTION = os.environ.get("PUBLIC_COLLECTION", "l1l1C1")

_tokens_path = os.environ.get("TOKENS_FILE", "tokens.txt")
TOKENS = (
    [t.strip() for t in Path(_tokens_path).read_text().splitlines() if t.strip()]
    if Path(_tokens_path).exists()
    else []
)


class AnonymousVisitor(HttpUser):
    """The open-web share of traffic (viral links, curious visitors)."""

    weight = 3
    # Humans read before they click; a load test without think time measures
    # the wrong thing (connection churn, not capacity).
    wait_time = between(2, 8)

    @task(5)
    def browse_public_collection(self):
        self.client.get(f"/api/v1/collections/{PUBLIC_COLLECTION}/",
                        name="/collections/{code} [anon]")

    @task(2)
    def read_a_thing(self):
        with self.client.get(
            f"/api/v1/collections/{PUBLIC_COLLECTION}/",
            name="/collections/{code} [anon]", catch_response=True,
        ) as res:
            things = (res.json() or {}).get("things", []) if res.ok else []
            if things:
                code = random.choice(things)["code"]
                self.client.get(f"/api/v1/things/{code}/", name="/things/{code} [anon]")

    @task(1)
    def legal_and_health(self):
        self.client.get("/api/v1/health/", name="/health")


class AuthenticatedMember(HttpUser):
    """Members with a session: dashboard reads dominate, writes are rare."""

    weight = 2
    wait_time = between(3, 10)

    def on_start(self):
        if not TOKENS:
            # No tokens provided: contribute anonymous pressure instead of
            # producing a wall of misleading 401s.
            self.token = None
            return
        self.token = random.choice(TOKENS)
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(5)
    def dashboard(self):
        if not self.token:
            return
        self.client.get("/api/v1/auth/me/", name="/auth/me")
        self.client.get("/api/v1/collections/", name="/collections [own]")
        self.client.get("/api/v1/invited-collections/", name="/invited-collections")

    @task(3)
    def read_shared_collection(self):
        if not self.token:
            return
        self.client.get(f"/api/v1/collections/{PUBLIC_COLLECTION}/",
                        name="/collections/{code} [member]")

    @task(1)
    def my_bookings(self):
        if not self.token:
            return
        self.client.get("/api/v1/my-bookings/", name="/my-bookings")

    @task(1)
    def ask_a_question(self):
        """The write path — rate-limited in prod config; on staging either
        disable RATELIMIT_ENABLE or accept 429s as part of the measurement
        (they are the throttle doing its job, not a server failure)."""
        if not self.token:
            return
        with self.client.get(
            f"/api/v1/collections/{PUBLIC_COLLECTION}/",
            name="/collections/{code} [member]", catch_response=True,
        ) as res:
            things = (res.json() or {}).get("things", []) if res.ok else []
        if things:
            code = random.choice(things)["code"]
            with self.client.post(
                f"/api/v1/things/{code}/faq/",
                json={"question": f"Load test q{random.randint(1, 9999)}"},
                name="/things/{code}/faq [write]", catch_response=True,
            ) as res:
                if res.status_code == 429:
                    res.success()  # the rate limiter answering is expected behaviour
