from types import SimpleNamespace

import pytest

from lifecycle.config import Settings
from lifecycle.integrations import GoogleWorkspaceClient, OktaClient


class Response:
    def __init__(self, payload=None):
        self._payload = payload or {}
        self.content = b"{}"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return Response(self.responses.pop(0))


def test_okta_create_user_posts_profile_and_returns_id():
    session = FakeSession([{"id": "okta-1"}])
    settings = Settings(okta_org_url="https://tenant.okta.com", okta_api_token="secret")
    client = OktaClient(settings, session=session)
    result = client.create_user("Alex", "Rivera", "alex@example.com", "Temp123!")
    assert result == "okta-1"
    assert session.calls[0][0] == "POST"
    assert session.calls[0][2]["json"]["profile"]["login"] == "alex@example.com"


def test_okta_group_assignment_resolves_group_then_puts_membership():
    session = FakeSession([
        [{"id": "group-1", "profile": {"name": "engineering"}}],
        {},
    ])
    settings = Settings(okta_org_url="https://tenant.okta.com", okta_api_token="secret")
    client = OktaClient(settings, session=session)
    assert client.assign_group("user-1", "engineering") == "group-1"
    assert session.calls[1][0] == "PUT"
    assert "/users/user-1/groups/group-1" in session.calls[1][1]


def test_okta_deactivate_user_looks_up_then_deactivates():
    session = FakeSession([
        [{"id": "user-1", "profile": {"email": "leaver@example.com"}}],
        {},
    ])
    settings = Settings(okta_org_url="https://tenant.okta.com", okta_api_token="secret")
    client = OktaClient(settings, session=session)
    assert client.deactivate_user("leaver@example.com") == "user-1"
    assert "lifecycle/deactivate" in session.calls[1][1]


def test_okta_missing_group_fails_closed():
    session = FakeSession([[]])
    settings = Settings(okta_org_url="https://tenant.okta.com", okta_api_token="secret")
    with pytest.raises(RuntimeError, match="group not found"):
        OktaClient(settings, session=session).assign_group("user-1", "engineering")


def test_google_workspace_revokes_each_listed_oauth_token():
    class Request:
        def __init__(self, result=None):
            self.result = result or {}

        def execute(self):
            return self.result

    class Tokens:
        def __init__(self):
            self.deleted = []

        def list(self, userKey):
            assert userKey == "leaver@example.com"
            return Request({"items": [{"clientId": "client-a"}, {"clientId": "client-b"}]})

        def delete(self, userKey, clientId):
            self.deleted.append((userKey, clientId))
            return Request()

    tokens = Tokens()

    class Users:
        def tokens(self):
            return tokens

    class Service:
        def users(self):
            return Users()

    client = GoogleWorkspaceClient(Settings())
    client.service = Service()
    assert client.revoke_tokens("leaver@example.com") == 2
    assert [item[1] for item in tokens.deleted] == ["client-a", "client-b"]


def test_google_workspace_create_user_uses_password_change_policy():
    class Request:
        def execute(self):
            return {"id": "google-1"}

    class Users:
        def insert(self, body):
            assert body["primaryEmail"] == "alex@example.com"
            assert body["changePasswordAtNextLogin"] is True
            return Request()

    class Service:
        def users(self):
            return Users()

    client = GoogleWorkspaceClient(Settings(google_org_unit_path="/Staff"))
    client.service = Service()
    assert client.create_user("Alex", "Rivera", "alex@example.com", "Temp123!") == "google-1"
