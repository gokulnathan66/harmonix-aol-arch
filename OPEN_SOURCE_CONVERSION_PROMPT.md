# Prompt: Convert a Normal Repository into an Open Source Repository

Use this comprehensive prompt to transform any repository into a production-ready open source project. This prompt is based on best practices and includes all essential components for open source success.

---

## Instructions

Transform the current repository into a professional, community-ready open source project by implementing the following components and best practices. Analyze the existing codebase structure, technology stack, and purpose, then create or update all necessary files and configurations.

---

## 1. LICENSE File

**Action Required:**
- Create a `LICENSE` file in the repository root
- Choose an appropriate license (MIT, Apache 2.0, GPL, etc.)
- Include copyright notice with current year and project name/contributors
- Ensure the license matches the project's goals and dependencies

**Template Structure:**
```
MIT License

Copyright (c) [YEAR] [PROJECT NAME] Contributors

[License text]
```

---

## 2. README.md Enhancement

**Action Required:**
- Update README.md with comprehensive project documentation
- Include the following sections:
  - Project title with badges (license, version, build status, etc.)
  - Clear description of what the project does
  - Features and capabilities
  - Architecture overview (with diagrams if applicable)
  - Quick start guide
  - Installation instructions
  - Usage examples
  - Configuration reference
  - API documentation (if applicable)
  - Development setup
  - Testing instructions
  - Contributing guidelines (link to CONTRIBUTING.md)
  - License information
  - Security policy (link to SECURITY.md)
  - Support and contact information

**Badges to Include:**
- License badge
- Build status (CI/CD)
- Code coverage
- Version badge
- Language/framework badges
- Contributions welcome badge

---

## 3. CONTRIBUTING.md

**Action Required:**
- Create `CONTRIBUTING.md` in repository root
- Include comprehensive contribution guidelines:

**Required Sections:**
- Table of Contents
- Getting Started (how to begin contributing)
- Development Setup (prerequisites, installation, environment setup)
- Code Standards (style guide, naming conventions, formatting)
- Testing Guidelines (how to write and run tests)
- Pull Request Process (branch naming, commit messages, PR template)
- Review Process (what reviewers look for)
- Architecture Guidelines (if applicable)
- Documentation Standards
- Questions and Support

**Include:**
- Prerequisites and setup instructions
- How to run tests locally
- Linting and code quality checks
- Commit message conventions (conventional commits)
- Branch naming conventions
- PR description template
- Code review expectations

---

## 4. CODE_OF_CONDUCT.md

**Action Required:**
- Create `CODE_OF_CONDUCT.md` in repository root
- Use Contributor Covenant 2.1 (industry standard)
- Include:
  - Our Pledge
  - Our Standards (acceptable and unacceptable behavior)
  - Enforcement Responsibilities
  - Scope
  - Enforcement (reporting process)
  - Enforcement Guidelines (consequences)
  - Attribution

**Important:**
- Update contact email for reporting violations
- Ensure enforcement guidelines are clear and fair

---

## 5. SECURITY.md

**Action Required:**
- Create `SECURITY.md` in repository root
- Include security policy and vulnerability reporting process

**Required Sections:**
- Supported Versions (which versions receive security updates)
- Reporting a Vulnerability
  - What NOT to do (don't open public issues)
  - What TO do (email process)
  - What to expect (response timeline)
- Security Best Practices (for users)
- Known Security Considerations
- Security Updates (how updates are released)

**Include:**
- Direct email contact for security issues
- Clear instructions on what information to include
- Timeline expectations for response and resolution

---

## 6. CHANGELOG.md

**Action Required:**
- Create `CHANGELOG.md` in repository root
- Follow Keep a Changelog format
- Use Semantic Versioning

**Format:**
```
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [Version] - YYYY-MM-DD
[Same sections]
```

---

## 7. GitHub Issue Templates

**Action Required:**
- Create `.github/ISSUE_TEMPLATE/` directory
- Create multiple issue templates:

### 7.1 Bug Report Template (`bug_report.md`)
**Include:**
- Description field
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, version, etc.)
- Configuration files (if applicable)
- Logs section
- Additional context
- Possible solution (optional)

### 7.2 Feature Request Template (`feature_request.md`)
**Include:**
- Feature description
- Problem statement
- Proposed solution
- Alternatives considered
- Additional context
- Implementation notes (optional)
- Related issues

### 7.3 Question Template (`question.md`)
**Include:**
- Question field
- Context
- What I've tried
- Additional information

### 7.4 Issue Template Config (`config.yml`)
**Include:**
- Disable blank issues (force template usage)
- Contact links:
  - Questions/Discussions → GitHub Discussions
  - Security Issues → Security Advisories

---

## 8. Pull Request Template

**Action Required:**
- Create `.github/PULL_REQUEST_TEMPLATE.md`
- Include comprehensive PR checklist

**Required Sections:**
- Description
- Type of Change (checkboxes):
  - Bug fix
  - New feature
  - Breaking change
  - Documentation update
  - Code refactoring
  - Performance improvement
  - Test addition/update
- Related Issues
- Changes Made (list)
- Testing (checkboxes and description)
- Checklist (self-review items)
- Screenshots (if applicable)
- Additional Notes

---

## 9. CI/CD Workflows

**Action Required:**
- Create `.github/workflows/` directory
- Set up comprehensive CI/CD pipeline

### 9.1 Main CI Workflow (`ci.yml`)
**Include Jobs:**
- **Lint Job:**
  - Checkout code
  - Set up language environment (Python/Node/etc.)
  - Install dependencies
  - Run linting tools (flake8, eslint, etc.)
  - Fail on linting errors

- **Test Job:**
  - Matrix strategy for multiple versions
  - Checkout code
  - Set up environment
  - Install dependencies and test tools
  - Run test suite
  - Generate coverage reports
  - Upload coverage to Codecov (optional)

- **Build Job:**
  - Depends on lint and test
  - Build Docker images (if applicable)
  - Build artifacts
  - Verify build succeeds

**Triggers:**
- Push to main/develop branches
- Pull requests to main/develop

### 9.2 Dependabot Auto-merge (Optional) (`dependabot-auto-merge.yml`)
- Auto-merge Dependabot PRs if tests pass
- Use squash merge strategy

---

## 10. Dependabot Configuration

**Action Required:**
- Create `.github/dependabot.yml`
- Configure for all package ecosystems used

**Include:**
- Package ecosystem (pip, npm, maven, etc.)
- Directory paths
- Update schedule (weekly/monthly)
- Open PR limit
- Labels for PRs
- Commit message prefix

**Example Ecosystems:**
- Python (pip)
- JavaScript (npm/yarn)
- GitHub Actions
- Docker
- Go modules
- Maven/Gradle

---

## 11. GitHub Funding Configuration (Optional)

**Action Required:**
- Create `.github/FUNDING.yml` if accepting sponsorships
- Configure funding platforms:
  - GitHub Sponsors
  - Patreon
  - Open Collective
  - Ko-fi
  - Custom URLs

---

## 12. .gitignore Enhancement

**Action Required:**
- Ensure `.gitignore` is comprehensive
- Include:
  - Language-specific ignores (Python: __pycache__, .pyc, venv, etc.)
  - IDE files (.vscode, .idea, etc.)
  - OS files (.DS_Store, Thumbs.db)
  - Environment files (.env, .env.local)
  - Build artifacts (dist/, build/, *.egg-info)
  - Test coverage (htmlcov/, .coverage)
  - Logs (*.log)

---

## 13. Repository Settings & Features

**Action Required:**
- Enable GitHub features:
  - ✅ Issues
  - ✅ Discussions (for questions and community)
  - ✅ Projects (optional)
  - ✅ Wiki (optional, prefer docs/ folder)
  - ✅ Security advisories
  - ✅ Dependency graph
  - ✅ Dependabot alerts

**Branch Protection:**
- Protect main/master branch
- Require PR reviews (at least 1)
- Require status checks to pass
- Require branches to be up to date
- Require conversation resolution

---

## 14. Documentation Structure

**Action Required:**
- Create `docs/` directory for comprehensive documentation
- Include:
  - Architecture documentation
  - API reference
  - Deployment guides
  - Configuration guides
  - Best practices
  - Troubleshooting guides
  - Examples and tutorials

---

## 15. Testing Infrastructure

**Action Required:**
- Ensure comprehensive test coverage
- Include:
  - Unit tests
  - Integration tests
  - End-to-end tests (if applicable)
  - Test fixtures and mocks
  - Test documentation

**Test Files:**
- Place in `tests/` directory
- Use naming convention: `test_*.py` or `*.test.js`
- Include test configuration files

---

## 16. Code Quality Tools

**Action Required:**
- Configure linting tools:
  - Python: flake8, black, pylint, mypy
  - JavaScript: ESLint, Prettier
  - Other languages: appropriate linters
- Add configuration files:
  - `.flake8`, `.pylintrc` (Python)
  - `.eslintrc.js`, `.prettierrc` (JavaScript)
  - `pyproject.toml` or `setup.cfg`

---

## 17. Package Management

**Action Required:**
- Maintain dependency files:
  - `requirements.txt` (Python)
  - `package.json` (Node.js)
  - `go.mod` (Go)
  - `pom.xml` or `build.gradle` (Java)
- Pin versions for reproducibility
- Include dev dependencies separately
- Document dependency management process

---

## 18. Docker Support (If Applicable)

**Action Required:**
- Create `Dockerfile` if containerization is needed
- Create `docker-compose.yml` for local development
- Include:
  - Multi-stage builds (optimize size)
  - Non-root user
  - Health checks
  - Proper labeling
- Document Docker usage in README

---

## 19. Version Management

**Action Required:**
- Use Semantic Versioning (MAJOR.MINOR.PATCH)
- Tag releases in Git
- Create GitHub Releases with:
  - Release notes
  - Changelog entries
  - Downloadable assets
- Update version in code/config files

---

## 20. Community Guidelines

**Action Required:**
- Set clear expectations:
  - Response time for issues/PRs
  - Code review process
  - Release schedule
  - Support policy
- Create community health files:
  - `SUPPORT.md` (optional)
  - `MAINTAINERS.md` (optional)

---

## 21. Security Best Practices

**Action Required:**
- Remove all secrets and credentials
- Use environment variables for configuration
- Add `.env.example` file
- Document security considerations
- Enable GitHub security features:
  - Dependabot alerts
  - Secret scanning
  - Code scanning (optional)

---

## 22. Accessibility & Inclusivity

**Action Required:**
- Ensure documentation is accessible
- Use inclusive language
- Provide multiple ways to contribute
- Welcome diverse contributors
- Make project beginner-friendly

---

## Implementation Checklist

Use this checklist to ensure all components are implemented:

- [ ] LICENSE file created with appropriate license
- [ ] README.md updated with comprehensive documentation
- [ ] CONTRIBUTING.md created with detailed guidelines
- [ ] CODE_OF_CONDUCT.md created (Contributor Covenant)
- [ ] SECURITY.md created with vulnerability reporting process
- [ ] CHANGELOG.md created (Keep a Changelog format)
- [ ] Issue templates created (bug, feature, question)
- [ ] Issue template config.yml created
- [ ] Pull request template created
- [ ] CI/CD workflow created (lint, test, build)
- [ ] Dependabot configuration created
- [ ] .gitignore reviewed and enhanced
- [ ] GitHub features enabled (Issues, Discussions, etc.)
- [ ] Branch protection rules configured
- [ ] Documentation structure created
- [ ] Test suite comprehensive and documented
- [ ] Code quality tools configured
- [ ] Dependencies properly managed
- [ ] Docker support (if applicable)
- [ ] Version management process defined
- [ ] Community guidelines established
- [ ] Security best practices implemented
- [ ] All secrets removed from repository

---

## Final Steps

1. **Review Everything:**
   - Read through all created files
   - Ensure consistency in naming and formatting
   - Verify all links work
   - Check for placeholder text that needs replacement

2. **Test the Setup:**
   - Create a test issue using templates
   - Create a test PR using template
   - Verify CI/CD runs successfully
   - Test local development setup

3. **Initial Commit:**
   - Commit all new files
   - Write clear commit message
   - Push to repository

4. **Announce:**
   - Create initial release
   - Share on social media/forums
   - Update project website (if applicable)

---

## Customization Notes

When using this prompt, customize:
- Project name and description
- Contact emails
- Technology stack specifics
- License type
- CI/CD tools based on stack
- Package managers used
- Documentation style
- Community guidelines

---

## Example Usage

```
I want to convert my [PROJECT_TYPE] repository into an open source project. 
Please analyze the current repository structure and implement all the components 
listed in the open source conversion prompt. The project is [BRIEF_DESCRIPTION], 
uses [TECH_STACK], and I want to use [LICENSE_TYPE] license. My contact email 
for security issues is [EMAIL].
```

---

This prompt ensures your repository follows industry best practices and is ready 
for open source collaboration, community contributions, and long-term maintenance.
