# Employee lifecycle automation

A Python reference implementation that coordinates security-relevant onboarding
and offboarding actions across Okta, Google Workspace, 1Password group/vault
access, MDM enrollment, and Slack notification.

> **Safe by default:** `INTEGRATION_MODE=mock` and `DRY_RUN=true`. No real
> accounts are changed unless real mode is explicitly configured. Offboarding
> additionally requires `--confirm` when `DRY_RUN=false`.

## Capabilities and API status

| Capability | Implementation | Real or mocked |
|---|---|---|
| Okta lifecycle | Create user, resolve and assign group; deactivate departing user | Real Okta Management API in `real` mode; deterministic mock otherwise |
| Google Workspace | Create account; list and delete all OAuth token grants | Real Admin SDK Directory API in `real` mode; mock otherwise |
| 1Password | Add hire to configured group; remove departing user from all shared vault memberships | Mock adapter by default |
| MDM | Build and log a Jamf/Intune-style enrollment invitation payload | Mock only; no device enrollment is actually initiated |
| Alert | Structured offboarding summary with actions, timestamp and failures | Real Slack incoming webhook when configured; otherwise logged |

### Important 1Password API limitation

The 1Password Connect API manages vault items, not user/group membership.
The Events API is for audit/event retrieval and is not a membership-write API.
Therefore this project deliberately uses a realistic mock for vault-group
membership instead of falsely claiming that Connect or Events can remove users.
For production, implement the adapter against your organization's supported
1Password SCIM Bridge / identity-provider provisioning workflow and configure
vault access for the relevant groups in 1Password. The `.env.example` includes
SCIM settings as deployment placeholders; the current adapter does not send
SCIM writes.

## Requirements

- Python 3.10+
- Okta API token and an Okta group for real Okta calls
- Google Workspace domain with Admin SDK enabled and a service account with
  domain-wide delegation for real Google calls
- Optional Slack incoming webhook

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

For Google Workspace real mode, install optional dependencies:

```bash
pip install 'google-api-python-client>=2.120' 'google-auth>=2.28'
```

Edit `.env`. Keep `INTEGRATION_MODE=mock` while testing. Never commit `.env`,
service-account keys, API tokens, or webhook URLs.

## Run locally

Mock onboarding:

```bash
python -m lifecycle.cli onboard --first-name Alex --last-name Rivera \\
  --email alex.rivera@example.com --password 'Use-a-temp-secret-123!'
```

Mock offboarding (dry-run):

```bash
python -m lifecycle.cli offboard --email departing@example.com
```

Execute real offboarding only after verifying tenant configuration and target:

```bash
# Set INTEGRATION_MODE=real and DRY_RUN=false in .env first.
python -m lifecycle.cli offboard --email departing@example.com --confirm
```

Real onboarding:

```bash
python -m lifecycle.cli onboard --first-name Alex --last-name Rivera \\
  --email alex.rivera@example.com --password 'Use-a-temp-secret-123!'
```

The password is supplied at runtime, not stored in source. For production,
prefer an invitation/activation flow or secret manager instead of passing
passwords in shell history. The sample creates an Okta user with an initial
password and creates a Google user; adapt the identity proofing and activation
process to your policy.

## Real API setup

### Okta

Create an API token with least-privilege permissions for user and group
management. Set `OKTA_ORG_URL`, `OKTA_API_TOKEN`, and `OKTA_GROUP_NAME`.
The integration calls:
- `POST /api/v1/users?activate=true` to create a user
- `GET /api/v1/groups?q=...` to resolve the group
- `PUT /api/v1/users/{userId}/groups/{groupId}` to assign membership
- `POST /api/v1/users/{userId}/lifecycle/deactivate?sendEmail=false`
  to deactivate a departing user

Use a dedicated test tenant first. Okta deactivation is consequential and may
not be reversible without reactivation/reprovisioning.

### Google Workspace

Enable the Admin SDK API. Create a service account, enable domain-wide
delegation, and authorize the required Directory API scopes in the Workspace
Admin console:
- `https://www.googleapis.com/auth/admin.directory.user`
- `https://www.googleapis.com/auth/admin.directory.user.security`

Set `GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_ADMIN_EMAIL`, and `GOOGLE_DOMAIN`.
The code creates a Directory user, lists OAuth tokens with
`users().tokens().list(userKey=...)`, then deletes each client token with
`users().tokens().delete(userKey=..., clientId=...)`.

Google's admin impersonation and scope approval are tenant-admin tasks; the
service account JSON must remain outside the repository.

### Slack

Create an incoming webhook and set `SLACK_WEBHOOK_URL`. The notifier posts a
structured JSON Block Kit message. If unset, the summary is written to logs.

## Safety and operational notes

- Dry-run suppresses all mutating calls. Reads may still occur in real mode
  where needed to resolve targets; this implementation skips integrations
  entirely in dry-run to avoid accidental API effects.
- Offboarding continues across systems after an individual failure and records
  each failure in the final alert. Review the summary and reconcile failed
  actions manually.
- Verify the departing user's immutable IDs and email before running.
- This is a starter workflow, not a complete HRIS/IGA platform. Add approvals,
  ticket references, manager/legal holds, asset return, session revocation,
  mailbox/Drive transfer, retention, and audit storage before production use.
- Never use broad administrator credentials where scoped roles are possible.

## Tests and lint

```bash
pytest -q
ruff check .
ruff format --check .
```

Tests use mocks and do not require external accounts or credentials.
