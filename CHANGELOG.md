# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.7] - 2025-05-14

### Added

- Docker image CI workflow for automated builds and pushes
- GitHub Container Registry (GHCR) integration
- Automated image tagging based on branch and commit
- Docker Buildx setup for multi-platform builds
- Cache optimization for faster builds
- Automated image publishing on push to main and develop branches

## [0.0.6] - 2025-05-13

### Added

- Initial public release of Evo AI platform
- FastAPI-based backend API
- JWT authentication with email verification
- Agent management (LLM, A2A, Sequential, Parallel, Loop, Workflow)
- Agent 2 Agent (A2A) protocol support (Google A2A spec)
- MCP server integration and management
- Custom tools management for agents
- Folder-based agent organization
- Secure API key management with encryption
- PostgreSQL and Redis integration
- Email notifications (SendGrid) with Jinja2 templates
- Audit log system for administrative actions
- LangGraph integration for workflow agents
- OpenTelemetry tracing and Langfuse integration
- Docker and Docker Compose support
- English documentation and codebase

### Changed

- N/A

### Fixed

- N/A

### Security

- JWT tokens with expiration and resource-based access control
- Secure password hashing (bcrypt)
- Account lockout after multiple failed login attempts
- Email verification and password reset flows

---

Older versions and future releases will be listed here.
