# Security Policy

## Supported Versions

BB-PAXDATA is a diplomatic discourse analysis engine. Security updates are applied to the following versions:

| Version | Supported |
| --- | --- |
| 1.x.x | :white_check_mark: |
| < 1.0 | :x: |

---

## Reporting a Vulnerability

We take the security of BB-PAXDATA seriously. If you believe you have found a security vulnerability, please report it to us as described below.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: `barisbozkurthello@gmail.com` (or the project's designated security contact).

You should receive a response within **48 hours**. If for some reason you do not, please follow up via email to ensure we received your original message.

Please include the following information in your report (to the extent you can provide):

- **Type of issue** (e.g., buffer overflow, SQL injection, cross-site scripting, API key exposure, etc.)
- **Full paths of source file(s)** related to the manifestation of the issue
- **The location of the affected source code** (tag/branch/commit or direct URL)
- **Any special configuration required** to reproduce the issue
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact of the issue**, including how an attacker might exploit it
- **Possible mitigations** you have identified

### Responsible Disclosure Policy

We ask that you:

- Give us reasonable time to investigate and mitigate the issue before disclosing it publicly.
- Make a good faith effort to avoid privacy violations, destruction of data, and interruption or degradation of our service.
- Only interact with accounts you own or with explicit permission from the account holder.
- Do not exploit the vulnerability beyond the minimum amount of testing required to prove its existence.

We will:

- Acknowledge receipt of your vulnerability report within 48 hours.
- Provide an estimated timeline for a fix within 7 days.
- Notify you when the vulnerability is fixed.
- Credit you in the security advisory (unless you prefer to remain anonymous).

---

## Security Considerations Specific to BB-PAXDATA

Given that BB-PAXDATA processes diplomatic transcripts, strategic communications, and potentially sensitive political texts, the following security domains are of critical importance:

### 1. LLM API Key Management

BB-PAXDATA integrates with multiple LLM providers (Anthropic Claude, Google Gemini, Groq, Ollama). API keys are a high-value target.

**Policies:**

- API keys **MUST NOT** be hardcoded in source code, committed to Git, or logged.
- Keys **MUST** be loaded via environment variables or a secrets manager (e.g., HashiCorp Vault, AWS Secrets Manager, or 1Password Secrets Automation).
- `.env` files **MUST** be listed in `.gitignore`.
- The `PromptRegistry` stores prompt SHA256 hashes for audit, but **never stores API keys**.
- Rotate LLM API keys quarterly.

**Implementation:**

```python
# CORRECT: Load from environment
import os
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# INCORRECT: Never do this
# ANTHROPIC_API_KEY = 'sk-ant-xxx...'
```

### 2. Diplomatic Data Sensitivity

Diplomatic transcripts may contain classified, restricted, or politically sensitive information.

**Policies:**

- All data at rest **MUST** be encrypted (SQLite: SQLCipher; PostgreSQL: transparent data encryption or filesystem-level encryption).
- Database backups **MUST** be encrypted.
- PII (Personally Identifiable Information) of diplomats, if present, **MUST** be handled in accordance with GDPR / applicable local privacy laws.
- The `Analysis` model is immutable by design (`frozen=True`), which prevents accidental data mutation and supports forensic integrity.
- Audit trails (`created_at`, `prompt_sha256`, `calculation_method`) **MUST NOT** be tampered with.

### 3. Database Security (SQLAlchemy 2.0 Async)

- **SQL Injection Prevention**: SQLAlchemy 2.0 ORM with parameterized queries is used throughout. Raw SQL is discouraged; if necessary, use `text()` with explicit parameter binding.
- **Connection Pooling**: Async connection pools are configured with `pool_pre_ping=True` and strict `max_overflow` limits to prevent connection exhaustion attacks.
- **Alembic Migrations**: Migration scripts are reviewed for destructive operations before deployment.

### 4. Input Validation & Deserialization

- **Pydantic v2** is the single source of truth for all domain models. All external input (API requests, LLM JSON responses, uploaded transcripts) passes through Pydantic validation.
- **RecoveryEngine** (6-Level JSON Recovery) is a security feature: it prevents malformed LLM outputs from crashing the pipeline, but **does not bypass validation**. All recovered data is re-validated against the Pydantic schema.
- **File Uploads**: Uploaded transcript files are validated for MIME type, size limits, and scanned for embedded scripts or macros before processing.

### 5. Async & Concurrency Safety

- All IO-bound operations (API calls, DB queries, file I/O) are strictly async (`async`/`await`).
- CPU-bound operations (numpy, scikit-learn, sentence-transformers) are offloaded to `asyncio.to_thread` or `ThreadPoolExecutor` to prevent event loop blocking.
- **Resource exhaustion**: `asyncio.Semaphore` is used to limit concurrent LLM API calls (default: 10 concurrent requests).

### 6. Dependency Security

- **Poetry** is used for deterministic dependency resolution. `poetry.lock` is committed and audited.
- **Dependabot** or `poetry audit` (via `pip-audit` / `safety`) is run weekly to detect known vulnerabilities in dependencies.
- **Ruff** and **MyPy** (strict mode) are part of CI/CD to catch type-safety and code-quality issues that could lead to security bugs.

### 7. Prompt Injection & LLM Security

- The `PromptRegistry` versions all prompts with SHA256 hashes, ensuring prompt integrity.
- User-provided text (transcripts) is **never** directly interpolated into LLM prompts without sanitization. All user input is treated as untrusted data.
- `temperature=0` is enforced for `LLMPositionEstimator` to maximize determinism and reduce adversarial output variance.
- LLM outputs are passed through the `RecoveryEngine` and then validated by Pydantic before entering the domain model.

### 8. Network & Infrastructure

- If deploying the FastAPI interface, use **HTTPS only** (TLS 1.2+).
- CORS policies must be explicitly configured; do not use `allow_origins=['*']` in production.
- Rate limiting (e.g., `slowapi` or nginx `limit_req`) should be applied to public endpoints to prevent abuse.
- Prometheus metrics endpoint (`/metrics`) **MUST NOT** be exposed publicly without authentication.

---

## Security Features

BB-PAXDATA implements the following security features by design:

| Feature | Description | Benefit |
| --- | --- | --- |
| **Immutable Domain Models** | All `Analysis`, `Segment`, `DKIResult` models use `frozen=True` | Prevents accidental mutation; supports forensic integrity |
| **SHA256 Audit Trail** | Every prompt and analysis result carries a SHA256 hash | Non-repudiation; reproducibility |
| **6-Level JSON Recovery** | `RecoveryEngine` handles malformed LLM outputs safely | Prevents pipeline crashes from untrusted LLM responses |
| **Structured Logging** | `structlog` with JSON output | Tamper-evident logs; SIEM integration |
| **Async Isolation** | CPU-bound work in threads, IO in async | Prevents DoS via event loop starvation |
| **Pydantic v2 Validation** | Strict schema enforcement on all boundaries | Type safety; injection prevention |
| **Protocol-Based Architecture** | Dependency Inversion via domain protocols | Testability; mock-based security testing |

---

## Acknowledgments

We thank the security researchers and the open-source community for helping keep BB-PAXDATA and its users safe. If you report a valid security issue, we will acknowledge your contribution in our release notes (unless you wish to remain anonymous).

---

*For questions about this security policy, contact: barisbozkurthello@gmail.com*
