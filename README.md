# Employee Lifecycle Automation

A Python-based security automation project that simulates Mal's employee onboarding and offboarding workflow across identity management, cloud access, endpoint management, and security notifications.

The goal is to automate essential employee lifecycle security tasks while maintaining visibility into completed actions, failures, and access changes.

## Project Overview

When a new employee joins an organization, multiple systems need to be configured to provide the appropriate access.

Similarly, when an employee leaves, their accounts, permissions, and access tokens must be revoked promptly to reduce security risks.

This project connects these workflows through a single Python automation script.

### Key Capabilities

| Capability | Onboarding | Offboarding |
|---|---|---|
| Okta | Create user and assign group | Deactivate user |
| Google Workspace | Create user account | Revoke OAuth tokens |
| 1Password | Assign user to vault group (mocked) | Simulate shared vault access removal |
| MDM | Generate enrollment invitation | Not currently implemented |
| Slack | Not currently implemented | Send structured offboarding notification |

## Architecture and Integrations

### 1. Okta – Identity Lifecycle Management

**Onboarding**
- Create a new Okta user.
- Resolve the configured Okta group.
- Assign the new user to the appropriate group.

**Offboarding**
- Locate the departing user.
- Deactivate their Okta account.

**Implementation:** Real Okta Management API integration is available in real mode. Mock behaviour is used for simulation.

### 2. Google Workspace – Account Provisioning

**Onboarding**
- Create a Google Workspace user account.

**Offboarding**
- Retrieve OAuth token grants associated with the user.
- Revoke the user's OAuth tokens.

**Implementation:** Google Admin SDK Directory API integration is available in real mode. Mock behaviour is used for simulation.

### 3. 1Password – Vault Access Management

**Onboarding**
- Simulate assigning the employee to the appropriate vault group.

**Offboarding**
- Simulate removing the departing employee from shared vault access.

**Implementation:** Currently mocked.

**Important API limitation:** The 1Password Connect API manages vault items, while the Events API provides audit and event information. Neither is a direct API for writing user or group membership changes.

For a production implementation, the appropriate approach is to integrate with a supported 1Password SCIM provisioning workflow or the organization's identity-provider provisioning solution.

The current project does not perform real 1Password SCIM writes.

### 4. MDM – Device Enrollment

The project simulates an endpoint enrollment trigger using a Jamf/Intune-style invitation payload.

The workflow generates a realistic payload and records the simulated response.

**Implementation:** Mocked. No actual Jamf or Microsoft Intune enrollment invitation is sent.

### 5. Slack – Security Notifications

The offboarding workflow generates a structured notification containing:

- Employee email address.
- Execution timestamp.
- Actions performed.
- Successful operations.
- Failed operations and error details.

**Implementation:** Slack incoming webhook integration is supported when configured. Otherwise, the notification is recorded in application logs.

## Project Structure

```text
Employee-lifecycle-automation/
│
├── src/
│   └── lifecycle/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py
│       ├── integrations.py
│       ├── workflows.py
│       └── cli.py
│
├── tests/
│   ├── test_workflows.py
│   └── test_integrations.py
│
├── .env.example
├── .gitignore
├── LICENSE
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.10 or later.
- Git.
- An Okta developer/test tenant for real Okta integration.
- A Google Workspace test environment for real Google integration.
- Optional Slack incoming webhook for real notifications.

Mock testing does not require external service accounts.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/farshinhashim/Employee-lifecycle-automation.git
```

### 2. Navigate to the project directory

```bash
cd Employee-lifecycle-automation
```

### 3. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Install the project

This step installs the local package in editable mode so that Python can import the `lifecycle` package.

```bash
python -m pip install -e .
```

### 6. Configure environment variables

Copy the example environment file:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS:**

```bash
cp .env.example .env
```

Edit `.env` and retain the safe testing configuration:

```env
INTEGRATION_MODE=mock
DRY_RUN=true
```

Do not commit `.env`, API tokens, service-account JSON files, or webhook URLs to GitHub.

## Running the Automation

### Onboarding Simulation

Example:

```bash
python -m lifecycle.cli onboard --first-name Alex --last-name Rivera --email alex@example.com --password "Temp-Pass-123!"
```

The workflow simulates:

1. Okta user creation.
2. Okta group assignment.
3. Google Workspace account creation.
4. 1Password vault-group assignment.
5. MDM enrollment invitation generation.

### Offboarding Simulation

Example:

```bash
python -m lifecycle.cli offboard --email alex@example.com
```

The workflow simulates:

1. Okta account deactivation.
2. Google Workspace OAuth token revocation.
3. 1Password shared vault access removal.
4. Slack offboarding notification.

The final report includes the execution status, actions, timestamp, and failures.

### Real Integration Execution

Real API execution requires the appropriate tenant configuration and credentials.

For real onboarding and offboarding:

1. Configure the required API credentials.
2. Set `INTEGRATION_MODE=real`.
3. Review the target employee and permissions.
4. Set `DRY_RUN=false` only when you are ready to execute real operations.

For real offboarding, the CLI additionally requires explicit confirmation:

```bash
python -m lifecycle.cli offboard --email departing@example.com --confirm
```

**Important:** Do not test real account creation, deactivation, or token revocation against production accounts. Use dedicated test tenants and accounts.

The onboarding password is currently supplied through the CLI argument. Avoid using real employee passwords or reusable secrets in shell commands because command history and process information may expose them.

## Real API Configuration

### Okta

Configure the following environment variables:

```env
OKTA_ORG_URL=
OKTA_API_TOKEN=
OKTA_GROUP_NAME=
```

The integration supports:

- Creating users.
- Searching for groups.
- Assigning users to groups.
- Deactivating users.

Use an API token with the minimum permissions required.

### Google Workspace

Google Workspace integration uses the Admin SDK Directory API.

Required configuration:

```env
GOOGLE_SERVICE_ACCOUNT_FILE=
GOOGLE_ADMIN_EMAIL=
GOOGLE_DOMAIN=
```

The service account must have domain-wide delegation enabled and the required Directory API scopes authorized by a Workspace administrator.

Supported operations:

- Create Workspace users.
- List OAuth token grants.
- Delete OAuth token grants.

Keep service-account credentials outside the repository.

### Slack

Configure an incoming webhook:

```env
SLACK_WEBHOOK_URL=
```

When configured, the offboarding workflow sends a structured notification to Slack.

If no webhook is configured, the notification is recorded in application logs.

## Testing

The project includes automated tests using pytest.

Run all tests:

```bash
python -m pytest -v
```

Run Ruff lint checks:

```bash
ruff check .
```

Check formatting:

```bash
ruff format --check .
```

The tests use mocks and do not require real Okta, Google Workspace, 1Password, or MDM accounts.

## Security Considerations

- API credentials are loaded through environment variables.
- `.env` must never be committed to the repository.
- Use dedicated test accounts for integration testing.
- Use least-privilege API permissions.
- Offboarding should be reviewed before execution.
- Real account deactivation and OAuth token revocation are consequential operations.
- Failed operations should be reviewed and reconciled manually.
- The current MDM and 1Password integrations are simulations, not production provisioning.

This is a reference automation project and is not intended to replace a complete HRIS, Identity Governance and Administration (IGA), or endpoint management platform.

A production implementation should additionally consider approval workflows, audit-log retention, manager notifications, legal holds, asset recovery, mailbox and Drive ownership transfer, and exception handling.

## Future Improvements

- Complete automated integration testing.
- Production-ready 1Password SCIM provisioning.
- Real Jamf or Microsoft Intune integration.
- Improved onboarding and offboarding reporting.
- Enhanced audit logging.
- Approval-based offboarding workflows.
- Secure password and credential handling.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
