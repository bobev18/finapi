# Decision Log: FinAPI

This document logs significant architectural and configuration decisions.

---

## 1. Web Framework: FastAPI
- **Status**: Decided
- **Context**: The requirements specify at least two Python services communicating via REST.
- **Decision**: Use **FastAPI** for both Service A and Service B.
- **Consequences**:
  - Out-of-the-box OpenAPI documentation (`/docs` and `/redoc`).
  - Strict type checking and request validation via Pydantic.
  - Performance improvements from native asynchronous handlers.

---

## 2. Storage & Caching: SQLite with SQLAlchemy/SQLModel
- **Status**: Decided
- **Context**: Market data calls to external APIs must be cached locally to prevent rate limiting.
- **Decision**: Use **SQLite** for cached data persistence, accessed via SQLAlchemy or SQLModel.
- **Consequences**:
  - Lightweight, file-based setup with no external server required.
  - Easy schema changes and migrations.
  - Reliable query support for cache lookup and TTL validation.

---

## 3. Git Identity Configuration (Local)
- **Status**: Decided & Implemented
- **Context**: The user wanted commits pushed under the identity `bobev18@gmail.com` with user name `bobev18`.
- **Decision**: Set the Git configurations locally (`git config user.name "bobev18"` and `git config user.email "bobev18@gmail.com"`).
- **Consequences**:
  - Global system settings remain unaffected.
  - All future commits in this project will correctly attribute to the user.

---

## 4. Personal Access Token (PAT) for GitHub Auth
- **Status**: Decided & Implemented
- **Context**: The user provided a fine-grained GitHub PAT for authentication.
- **Decision**: Use HTTPS remote URL with the embedded PAT to perform local pushes.
- **Consequences**:
  - Git remote is set up as `https://<PAT>@github.com/bobev18/finapi.git`.
  - Pushing succeeds without interactive prompts or GUI popups.
