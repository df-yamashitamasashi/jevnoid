import json

import httpx
import pytest

import src.adapters.kv_publisher as kv
import src.infrastructure.lambda_handler as lh
from src.adapters.kv_publisher import CloudflareKVPublisher
from src.adapters.secrets import read_secret
from src.adapters.vital_repo import InMemoryVitalRepository
from src.usecases.vitals_snapshot import build_vitals_snapshot


async def test_snapshot_exposes_birth_time_for_every_organism():
    repo = InMemoryVitalRepository()
    organisms = await repo.get_all_organisms()
    snapshot = build_vitals_snapshot(organisms, [], jev_connected=False)
    assert len(snapshot["organisms"]) == len(organisms) > 0
    assert all(o["born_at"] == org.created_at for o, org in zip(snapshot["organisms"], organisms))
    json.dumps(snapshot)


def test_publisher_puts_raw_json_with_bearer_token(monkeypatch):
    captured = {}

    def fake_put(url, headers, content, timeout):
        captured.update(url=url, headers=headers, body=json.loads(content))
        return httpx.Response(200, request=httpx.Request("PUT", url))

    monkeypatch.setattr(kv.httpx, "put", fake_put)
    CloudflareKVPublisher("acct", "ns", "tok").publish({"hello": "世界"})
    assert captured["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/storage/kv/namespaces/ns/values/snapshot"
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert captured["body"] == {"hello": "世界"}


class StubHeartbeat:
    async def pulse_all(self):
        return [{"species": "gaia", "daughter_born": None}, {"species": "cosmo", "daughter_born": "Cosmo-Mutant (Gen 1)"}]


class RecordingPublisher:
    def __init__(self, fail=False):
        self.fail, self.snapshots = fail, []

    def publish(self, snapshot):
        if self.fail:
            raise RuntimeError("cloudflare down")
        self.snapshots.append(snapshot)


@pytest.fixture
def wired_handler(monkeypatch):
    def wire(publisher):
        class Brain:
            is_connected = False
        monkeypatch.setattr(lh, "get_dependencies", lambda: (InMemoryVitalRepository(), Brain(), StubHeartbeat(), publisher))
    return wire


def test_handler_ignores_anything_but_eventbridge(wired_handler):
    publisher = RecordingPublisher()
    wired_handler(publisher)
    assert lh.handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": "/"}, None) == {"status": "ignored"}
    assert lh.handler({"source": "attacker", "detail-type": "Scheduled Event"}, None) == {"status": "ignored"}
    assert publisher.snapshots == []


def test_handler_publishes_snapshot_after_pulse(wired_handler):
    publisher = RecordingPublisher()
    wired_handler(publisher)
    result = lh.handler({"source": "aws.events"}, None)
    assert result == {"status": "pulsed", "organisms": 2, "births": ["Cosmo-Mutant (Gen 1)"], "published": True}
    assert publisher.snapshots[0]["organisms"]


def test_handler_survives_publish_failure_without_raising(wired_handler):
    wired_handler(RecordingPublisher(fail=True))
    assert lh.handler({"source": "aws.events"}, None)["published"] is False


def test_read_secret_prefers_env_then_ssm(monkeypatch):
    monkeypatch.setenv("DEMO_SECRET", "from-env")
    assert read_secret("DEMO_SECRET", "DEMO_SECRET_PARAM") == "from-env"

    monkeypatch.delenv("DEMO_SECRET")
    monkeypatch.setenv("DEMO_SECRET_PARAM", "/demo/secret")
    calls = []

    class FakeSSM:
        def get_parameter(self, Name, WithDecryption):
            calls.append((Name, WithDecryption))
            return {"Parameter": {"Value": "from-ssm\n"}}

    import boto3
    monkeypatch.setattr(boto3, "client", lambda service: FakeSSM())
    assert read_secret("DEMO_SECRET", "DEMO_SECRET_PARAM") == "from-ssm"
    assert calls == [("/demo/secret", True)]

    monkeypatch.delenv("DEMO_SECRET_PARAM")
    assert read_secret("DEMO_SECRET", "DEMO_SECRET_PARAM") is None
