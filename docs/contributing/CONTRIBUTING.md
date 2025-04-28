# Contributing to Evo AI

Thank you for your interest in contributing to Evo AI! This document provides guidelines and instructions for contributing to the project.

## Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis
- Git

### Setup Development Environment

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/evo-ai.git
   cd evo-ai
   ```
3. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate  # Windows
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
5. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```
6. Run database migrations:
   ```bash
   make alembic-upgrade
   ```

## Development Workflow

### Branching Strategy

- `main` - Main branch, contains stable code
- `feature/*` - For new features
- `bugfix/*` - For bug fixes
- `docs/*` - For documentation changes

### Creating a New Feature

1. Create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Run tests:
   ```bash
   make test
   ```
4. Commit your changes:
   ```bash
   git commit -m "Add feature: description of your changes"
   ```
5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
6. Create a Pull Request to the main repository

## Coding Standards

### Python Code Style

- Follow PEP 8
- Use 4 spaces for indentation
- Maximum line length of 79 characters
- Use descriptive variable names
- Write docstrings for all functions, classes, and modules

### Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- First line should be a summary under 50 characters
- Reference issues and pull requests where appropriate

## Testing

- All new features should include tests
- All bug fixes should include tests that reproduce the bug
- Run the full test suite before submitting a PR

## Documentation

- Update documentation for any new features or API changes
- Documentation should be written in English
- Use Markdown for formatting

## Pull Request Process

1. Ensure your code follows the coding standards
2. Update the documentation as needed
3. Include tests for new functionality
4. Ensure the test suite passes
5. Update the CHANGELOG.md if applicable
6. The PR will be reviewed by maintainers
7. Once approved, it will be merged into the main branch

## Code Review Process

All submissions require review. We use GitHub pull requests for this purpose.

Reviewers will check for:
- Code quality and style
- Test coverage
- Documentation
- Appropriateness of the change

## Community

- Be respectful and considerate of others
- Help others who have questions
- Follow the code of conduct

Thank you for contributing to Evo AI! 