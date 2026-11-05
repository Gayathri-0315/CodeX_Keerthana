"""Apply-link check: reachable links pass, broken ones warn, private addresses are never contacted."""

from unittest.mock import patch

import httpx

from app.services import links

from .conftest import login


def _resp(status, location=None):
    return httpx.Response(status, headers={"location": location} if location else {}, request=httpx.Request("GET", "https://x.test"))


def test_private_and_local_addresses_are_refused_without_a_request():
    with patch.object(httpx.Client, "get") as get:
        for url in ("http://localhost:8000/admin", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data", "http://10.0.0.5/",
                    "ftp://example.org/file", "javascript:alert(1)"):
            assert links.check(url) is not None, url
        get.assert_not_called()


def test_status_codes():
    with patch.object(links, "_public_host", return_value=True):
        for status, ok in ((200, True), (403, True), (405, True), (404, False), (410, False), (503, False)):
            with patch.object(httpx.Client, "get", return_value=_resp(status)):
                assert (links.check("https://club.example.org/apply") is None) is ok, status
        with patch.object(httpx.Client, "get", side_effect=httpx.ConnectError("no")):
            assert links.check("https://club.example.org/apply") == links.UNREACHABLE


def test_redirects_to_private_addresses_are_refused():
    hosts = {"club.example.org": True, "127.0.0.1": False}
    with patch.object(links, "_public_host", side_effect=lambda h: hosts[h]), \
         patch.object(httpx.Client, "get", return_value=_resp(302, "http://127.0.0.1/secret")) as get:
        assert links.check("https://club.example.org/apply") == links.UNREACHABLE
        assert get.call_count == 1


def test_endpoint_is_for_organizers(client):
    assert client.post("/api/organizer/check-link", json={"url": "https://example.org"}).status_code == 401
    login(client, "student")
    assert client.post("/api/organizer/check-link", json={"url": "https://example.org"}).status_code == 403
    login(client, "organizer")
    with patch.object(links, "check", return_value=None):
        assert client.post("/api/organizer/check-link", json={"url": "https://example.org"}).json() == {"ok": True, "reason": None}
