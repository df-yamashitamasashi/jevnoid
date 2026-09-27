import socket

import httpx
import pytest

import src.adapters.web_forager as wf
from src.adapters.web_forager import WebForager

REAL_ASYNC_CLIENT = httpx.AsyncClient


def fake_dns(mapping):
    def getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror("unknown host")
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in mapping[host]]
    return getaddrinfo


@pytest.mark.parametrize("url", [
    "ftp://example.com/file",
    "javascript:alert(1)",
    "http://user:pass@example.com/",
    "http://example.com:8080/",
    "https://example.com:22/",
    "http:///no-host",
])
def test_rejects_urls_outside_policy(url):
    assert WebForager._parse_fetchable(url) is None


@pytest.mark.parametrize("ips", [
    ["169.254.169.254"],
    ["127.0.0.1"],
    ["10.0.0.5"],
    ["192.168.1.10"],
    ["100.64.0.1"],
    ["::1"],
    ["::ffff:127.0.0.1"],
    ["93.184.216.34", "10.0.0.5"],
])
def test_rejects_non_public_resolution(monkeypatch, ips):
    monkeypatch.setattr(socket, "getaddrinfo", fake_dns({"evil.test": ips}))
    assert WebForager._pin_public_target("https://evil.test/page") is None


def test_pins_public_ipv4_and_ipv6(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", fake_dns({"v4.test": ["93.184.216.34"], "v6.test": ["2606:2800:220:1::1"]}))
    assert WebForager._pin_public_target("https://v4.test/a?b=1") == ("https://93.184.216.34/a?b=1", "v4.test")
    assert WebForager._pin_public_target("http://v6.test/") == ("http://[2606:2800:220:1::1]/", "v6.test")


def use_mock_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(wf.httpx, "AsyncClient", lambda **kw: REAL_ASYNC_CLIENT(transport=transport, **kw))


async def test_redirect_to_internal_host_is_not_followed(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", fake_dns({"public.test": ["93.184.216.34"], "internal.test": ["10.0.0.5"]}))
    seen = []

    def handler(request):
        seen.append((request.url.host, request.headers["host"]))
        return httpx.Response(302, headers={"location": "http://internal.test/admin"})

    use_mock_transport(monkeypatch, handler)
    assert await WebForager()._fetch_public("https://public.test/start") is None
    assert seen == [("93.184.216.34", "public.test")]


async def test_redirect_chain_is_capped(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", fake_dns({"loop.test": ["93.184.216.34"]}))
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(302, headers={"location": f"/hop{len(calls)}"})

    use_mock_transport(monkeypatch, handler)
    assert await WebForager()._fetch_public("https://loop.test/") is None
    assert len(calls) == wf.MAX_REDIRECTS + 1


async def test_follows_public_redirect_and_caps_body(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", fake_dns({"a.test": ["93.184.216.34"], "b.test": ["93.184.216.35"]}))

    def handler(request):
        if request.headers["host"] == "a.test":
            return httpx.Response(301, headers={"location": "https://b.test/final"})
        return httpx.Response(200, content=b"x" * (wf.MAX_BODY_BYTES * 3))

    use_mock_transport(monkeypatch, handler)
    final_url, body = await WebForager()._fetch_public("https://a.test/")
    assert final_url == "https://b.test/final"
    assert len(body) == wf.MAX_BODY_BYTES
