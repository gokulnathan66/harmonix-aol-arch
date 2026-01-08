# Contributing to harmonix AOL Architecture

Thank you for your interest in contributing to the harmonix AOL Architecture! This document provides guidelines and best practices for contributing to this repository.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Creating a New Service](#creating-a-new-service)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Architecture Guidelines](#architecture-guidelines)

## Getting Started

Before contributing, please:

1. Read the [README.md](README.md) to understand the architecture
2. Review the [documentation](docs/) for detailed component information
3. Check existing [issues](../../issues) and [pull requests](../../pulls)

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/gokulnathan66/harmonix-aol-arch.git
cd harmonix-aol-arch

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-asyncio flake8
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_validators.py -v

# Run with coverage
pytest tests/ --cov=utils --cov-report=html
```

### Linting

```bash
# Check for syntax errors
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Full linting
flake8 . --count --max-complexity=10 --max-line-length=127 --statistics
```

## Creating a New Service

Use the provided script to create new AOL-compliant services:

```bash
./create-service.sh my-service-name [ServiceType]
```

**Service Types:**
- `Agent` - AI reasoning and decision-making service
- `Tool` - External API integration or utility service
- `Plugin` - Extensible functionality module
- `Service` - General microservice (default)

**Example:**
```bash
./create-service.sh sentiment-analyzer Agent
```

## Code Standards

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for function signatures
- Maximum line length: 127 characters
- Use docstrings for all public modules, functions, classes, and methods

### File Organization

```
service-name/
├── service/          # Main service implementation
├── utils/            # Utility modules
├── sidecar/          # Sidecar components
├── integration/      # External integrations
├── proto/            # Protocol buffers
├── tests/            # Service-specific tests
├── manifest.yaml     # Service manifest
├── config.yaml       # Runtime configuration
└── Dockerfile        # Container definition
```

### Naming Conventions

- **Services:** `kebab-case` (e.g., `sentiment-analyzer`)
- **Python files:** `snake_case` (e.g., `event_bus.py`)
- **Classes:** `PascalCase` (e.g., `EventBus`)
- **Functions/variables:** `snake_case` (e.g., `publish_event`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)

## Testing

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix (e.g., `test_validators.py`)
- Use descriptive test names that explain what is being tested
- Include both positive and negative test cases
- Mock external dependencies

### Test Structure

```python
import pytest
from utils.my_module import MyClass

class TestMyClass:
    """Test suite for MyClass"""
    
    def test_valid_input(self):
        """Test that valid input produces expected output"""
        # Arrange
        instance = MyClass()
        
        # Act
        result = instance.process("valid input")
        
        # Assert
        assert result == expected_output
    
    def test_invalid_input(self):
        """Test that invalid input raises appropriate error"""
        instance = MyClass()
        
        with pytest.raises(ValueError):
            instance.process("invalid input")
```

## Pull Request Process

### Before Submitting

1. **Update tests:** Add or update tests for your changes
2. **Run tests:** Ensure all tests pass locally
3. **Lint code:** Fix any linting errors
4. **Update documentation:** Update README.md and relevant docs
5. **Update manifest:** If adding features, update manifest schema

### PR Guidelines

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make atomic commits:**
   - Each commit should represent a single logical change
   - Write clear, descriptive commit messages
   - Format: `type: brief description`
   
   **Types:**
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Adding or updating tests
   - `refactor:` Code refactoring
   - `chore:` Maintenance tasks

3. **Push and create PR:**
   ```bash
   git push origin feature/my-feature
   ```

4. **PR Description:**
   - Describe what changes were made and why
   - Reference related issues
   - Include screenshots for UI changes
   - List any breaking changes

### Review Process

- All PRs require at least one approval
- CI checks must pass
- Address review comments promptly
- Keep PRs focused and reasonably sized

## Architecture Guidelines

### Service Design Principles

1. **Loose Coupling:** Services should communicate via events and pub-sub
2. **Single Responsibility:** Each service should have one clear purpose
3. **Fail Gracefully:** Use circuit breakers and retries
4. **Observable:** Include logging, metrics, and tracing
5. **Declarative:** Use manifest.yaml to declare capabilities

### Manifest Best Practices

```yaml
# Always declare dependencies
dependencies:
  - service: "aol-core"
    optional: false

# Enable data storage only if needed
dataRequirements:
  enabled: true
  collections:
    - name: "my-data"
      schema: {...}

# Use pub-sub for async coordination
communication:
  pubsub:
    enabled: true
    subscribe:
      - "orchestration.commands"
    publish:
      - "task.completed"
```

### Port Allocation

Follow these port ranges:
- **gRPC:** 50051-50099
- **Sidecar:** 50100-50199
- **Health:** 50200-50299
- **Metrics:** 8080-8099

### Error Handling

```python
# Use structured logging
logger.error("Failed to process request", extra={
    'request_id': request_id,
    'error': str(e)
})

# Implement retries with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def call_external_service():
    # Implementation
    pass
```

## Documentation

### Code Documentation

- Use docstrings for all public APIs
- Include parameter types and return types
- Provide usage examples for complex functions

```python
def validate_manifest(manifest_path: str, strict: bool = False) -> ValidationResult:
    """
    Validate a manifest file against the AOL schema.
    
    Args:
        manifest_path: Path to the manifest.yaml file
        strict: If True, unknown fields are flagged as errors
        
    Returns:
        ValidationResult containing validation status and issues
        
    Example:
        >>> result = validate_manifest('manifest.yaml')
        >>> if not result.valid:
        ...     print(result.errors)
    """
```

### Updating Documentation

When adding features:
- Update relevant docs in `docs/`
- Add examples to `examples/`
- Update README.md if it affects usage
- Update manifest schema if needed

## Questions?

- Open an [issue](../../issues) for bugs or feature requests
- Check [documentation](docs/) for architecture details
- Review existing code for examples

Thank you for contributing! 🚀
