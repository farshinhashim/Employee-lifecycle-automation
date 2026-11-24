import logging
from typing import Any

import requests

from lifecycle.config import Settings

LOG = logging.getLogger(__name__)


class OktaClient:
    def __init__(self, settings: Settings, session: Any = requests):
        self.settings = settings
        self.session = session
        self.base = settings.okta_org_url

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(
            method,
            f"{self.base}{path}",
            headers={
                "Authorization": f"SSWS {self.settings.okta_api_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=20,
            **kwargs,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def create_user(
        self, first_name: str, last_name: str, email: str, password: str
    ) -> str:
        body = {
            "profile": {
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "login": email,
            },
            "credentials": {"password": {"value": password}},
        }
        user = self._request("POST", "/api/v1/users?activate=true", json=body)
        return user["id"]

    def assign_group(self, user_id: str, group_name: str) -> str:
        groups = self._request(
            "GET", "/api/v1/groups", params={"q": group_name, "limit": 200}
        )
        match = next(
            (
                group
                for group in groups
                if group.get("profile", {}).get("name", "").lower()
                == group_name.lower()
            ),
            None,
        )
        if not match:
            raise RuntimeError(f"Okta group not found: {group_name}")
        self._request("PUT", f"/api/v1/users/{user_id}/groups/{match['id']}")
        return match["id"]

    def deactivate_user(self, email: str) -> str:
        users = self._request(
            "GET", "/api/v1/users", params={"search": f'profile.login eq "{email}"'}
        )
        user = next(
            (item for item in users if item.get("profile", {}).get("email") == email),
            None,
        )
        if not user:
            raise RuntimeError(f"Okta user not found: {email}")
        self._request(
            "POST",
            f"/api/v1/users/{user['id']}/lifecycle/deactivate?sendEmail=false",
        )
        return user["id"]


class GoogleWorkspaceClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.service = None

    def _service(self) -> Any:
        if self.service is None:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
            except ImportError as exc:
                raise RuntimeError(
                    "Install Google extras: "
                    "pip install google-api-python-client google-auth"
                ) from exc

            scopes = [
                "https://www.googleapis.com/auth/admin.directory.user",
                "https://www.googleapis.com/auth/admin.directory.user.security",
            ]

            credentials = service_account.Credentials.from_service_account_file(
                self.settings.google_service_account_file,
                scopes=scopes,
            ).with_subject(self.settings.google_admin_email)

            self.service = build(
                "admin",
                "directory_v1",
                credentials=credentials,
                cache_discovery=False,
            )

        return self.service

    def create_user(
        self, first_name: str, last_name: str, email: str, password: str
    ) -> str:
        result = (
            self._service()
            .users()
            .insert(
                body={
                    "primaryEmail": email,
                    "name": {"givenName": first_name, "familyName": last_name},
                    "password": password,
                    "changePasswordAtNextLogin": True,
                    "orgUnitPath": self.settings.google_org_unit_path,
                }
            )
            .execute()
        )
        return result["id"]

    def revoke_tokens(self, email: str) -> int:
        service = self._service()
        token_data = service.users().tokens().list(userKey=email).execute()
        tokens = token_data.get("items", [])

        for token in tokens:
            service.users().tokens().delete(
                userKey=email,
                clientId=token["clientId"],
            ).execute()

        return len(tokens)


class OnePasswordMock:
    """Honest mock: Connect and Events APIs do not write group membership."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.memberships: dict[str, set[str]] = {}

    def assign_new_hire(self, email: str) -> str:
        self.memberships.setdefault(email, set()).add(self.settings.onepassword_group)
        LOG.info(
            "MOCK 1Password: %s added to group %s",
            email,
            self.settings.onepassword_group,
        )
        return self.settings.onepassword_group

    def remove_from_shared_vaults(self, email: str) -> list[str]:
        vaults = list(self.settings.onepassword_vault_ids)
        self.memberships.pop(email, None)
        LOG.info("MOCK 1Password: %s removed from shared vaults %s", email, vaults)
        return vaults


class MDMClient:
    def __init__(self, provider: str = "jamf"):
        self.provider = provider

    def send_enrollment_invitation(
        self, email: str, first_name: str, last_name: str
    ) -> dict:
        payload = {
            "provider": self.provider,
            "recipient": email,
            "user": {"first_name": first_name, "last_name": last_name},
            "enrollment": {
                "method": "email_invitation",
                "platforms": ["macOS", "iOS"]
                if self.provider == "jamf"
                else ["Windows", "iOS", "Android"],
                "expires_in_hours": 72,
                "require_user_authentication": True,
            },
            "metadata": {"source": "mal-employee-lifecycle", "mode": "mock"},
        }
        response = {
            "http_status": 202,
            "request_id": "mock-mdm-2026-0001",
            "accepted": True,
        }
        LOG.info("MOCK MDM invitation payload=%s response=%s", payload, response)
        return {"payload": payload, "response": response}


class SlackNotifier:
    def __init__(self, webhook_url: str = "", session: Any = requests):
        self.webhook_url = webhook_url
        self.session = session

    def send(self, report: dict) -> bool:
        if not self.webhook_url:
            LOG.info("Offboarding summary (Slack not configured): %s", report)
            return False

        actions = report.get("actions", [])
        lines = [
            f"*Offboarding {report['status']}*",
            f"*User:* {report['user']}",
            f"*Timestamp:* {report['timestamp']}",
            "*Actions:*",
        ]
        lines.extend(
            f"• {action['system']} / {action['action']}: "
            f"{'OK' if action['success'] else 'FAILED'}"
            + (f" — {action['detail']}" if action.get("detail") else "")
            for action in actions
        )

        if report.get("failures"):
            lines.append("*Failures:* " + "; ".join(report["failures"]))

        response = self.session.post(
            self.webhook_url,
            json={"text": "\n".join(lines)},
            timeout=15,
        )
        response.raise_for_status()
        return True
