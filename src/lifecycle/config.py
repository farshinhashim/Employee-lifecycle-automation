import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("INTEGRATION_MODE", "mock").lower()
    dry_run: bool = env_bool("DRY_RUN", True)
    okta_org_url: str = os.getenv("OKTA_ORG_URL", "").rstrip("/")
    okta_api_token: str = os.getenv("OKTA_API_TOKEN", "")
    okta_group_name: str = os.getenv("OKTA_GROUP_NAME", "engineering")
    google_service_account_file: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    google_admin_email: str = os.getenv("GOOGLE_ADMIN_EMAIL", "")
    google_domain: str = os.getenv("GOOGLE_DOMAIN", "")
    google_org_unit_path: str = os.getenv("GOOGLE_ORG_UNIT_PATH", "/")
    onepassword_group: str = os.getenv("ONEPASSWORD_NEW_HIRE_GROUP", "engineering")
    onepassword_vault_ids: tuple = tuple(
        item.strip()
        for item in os.getenv("ONEPASSWORD_SHARED_VAULT_IDS", "engineering,shared").split(",")
        if item.strip()
    )
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    mdm_provider: str = os.getenv("MDM_PROVIDER", "jamf").lower()

    def validate_real(self) -> None:
        if self.mode != "real":
            return
        missing = []
        if not self.okta_org_url or not self.okta_api_token:
            missing.append("OKTA_ORG_URL/OKTA_API_TOKEN")
        if not self.google_service_account_file or not self.google_admin_email:
            missing.append("GOOGLE_SERVICE_ACCOUNT_FILE/GOOGLE_ADMIN_EMAIL")
        if missing:
            raise ValueError("Missing real integration settings: " + ", ".join(missing))
