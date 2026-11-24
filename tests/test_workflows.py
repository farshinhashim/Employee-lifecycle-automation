from types import SimpleNamespace

from lifecycle.config import Settings
from lifecycle.integrations import MDMClient, OnePasswordMock, SlackNotifier
from lifecycle.workflows import LifecycleWorkflow


class FakeOkta:
    def __init__(self):
        self.created = []
        self.deactivated = []

    def create_user(self, first, last, email, password):
        self.created.append(email)
        return "okta-user-123"

    def assign_group(self, user_id, group):
        return "group-123"

    def deactivate_user(self, email):
        self.deactivated.append(email)
        return "okta-user-123"


class FakeGoogle:
    def __init__(self):
        self.created = []
        self.revoked = []

    def create_user(self, first, last, email, password):
        self.created.append(email)
        return "google-user-123"

    def revoke_tokens(self, email):
        self.revoked.append(email)
        return 2


class FakeNotifier:
    def __init__(self):
        self.reports = []

    def send(self, report):
        self.reports.append(report)
        return True


def real_settings():
    return Settings(mode="mock", dry_run=False, okta_group_name="engineering")


def test_onboarding_runs_all_major_steps():
    okta, google = FakeOkta(), FakeGoogle()
    op = OnePasswordMock(real_settings())
    workflow = LifecycleWorkflow(
        real_settings(),
        okta=okta,
        google=google,
        onepassword=op,
        mdm=MDMClient("jamf"),
        notifier=FakeNotifier(),
    )
    result = workflow.onboard("Alex", "Rivera", "alex@example.com", "Temp-Pass-123!")
    assert result["status"] == "completed"
    assert okta.created == ["alex@example.com"]
    assert google.created == ["alex@example.com"]
    assert "engineering" in op.memberships["alex@example.com"]
    assert any(
        a.action == "send_enrollment_invitation"
        for a in [SimpleNamespace(**item) for item in result["actions"]]
    )


def test_offboarding_deactivates_revokes_and_notifies():
    okta, google, notifier = FakeOkta(), FakeGoogle(), FakeNotifier()
    op = OnePasswordMock(real_settings())
    op.memberships["leaver@example.com"] = {"engineering", "shared"}
    workflow = LifecycleWorkflow(
        real_settings(), okta=okta, google=google, onepassword=op, notifier=notifier
    )
    result = workflow.offboard("leaver@example.com")
    assert result["status"] == "completed"
    assert okta.deactivated == ["leaver@example.com"]
    assert google.revoked == ["leaver@example.com"]
    assert "leaver@example.com" not in op.memberships
    assert notifier.reports


def test_dry_run_makes_no_integration_calls():
    settings = Settings(mode="mock", dry_run=True)
    okta, google = FakeOkta(), FakeGoogle()
    workflow = LifecycleWorkflow(settings, okta=okta, google=google)
    result = workflow.offboard("leaver@example.com")
    assert result["status"] == "completed"
    assert all(action["simulated"] for action in result["actions"])
    assert not okta.deactivated
    assert not google.revoked


def test_mdm_payload_is_realistic_and_accepted():
    result = MDMClient("intune").send_enrollment_invitation(
        "alex@example.com", "Alex", "Rivera"
    )
    assert result["payload"]["recipient"] == "alex@example.com"
    assert "Windows" in result["payload"]["enrollment"]["platforms"]
    assert result["response"]["http_status"] == 202


def test_slack_notifier_without_webhook_is_safe():
    assert SlackNotifier("").send({"user": "x", "actions": [], "failures": []}) is False


def test_slack_failure_is_recorded_without_aborting_offboarding():
    class BrokenNotifier:
        def send(self, report):
            raise RuntimeError("webhook unavailable")

    workflow = LifecycleWorkflow(
        real_settings(),
        okta=FakeOkta(),
        google=FakeGoogle(),
        onepassword=OnePasswordMock(real_settings()),
        notifier=BrokenNotifier(),
    )
    result = workflow.offboard("leaver@example.com")
    assert result["status"] == "completed_with_errors"
    assert any(
        item["system"] == "slack" and not item["success"] for item in result["actions"]
    )
