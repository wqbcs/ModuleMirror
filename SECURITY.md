# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in ModuleMirror, please follow responsible disclosure:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email security reports to the maintainers (see CODEOWNERS)
3. Include the following information:
   - Type of vulnerability (e.g., injection, SSRF, privilege escalation)
   - Affected component and version
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

## Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Status Updates**: Every 7 days until resolution
- **Resolution Target**: 30 days for P0/P1, 90 days for P2

## Security Features

ModuleMirror implements the following security controls:

- **Input Validation**: Path traversal, command injection, ReDoS prevention
- **Authentication**: JWT + RBAC with token blacklisting
- **Rate Limiting**: Tiered rate limiting (user/endpoint/operation)
- **SSRF Protection**: GitHub URL whitelist + private IP filtering
- **Audit Logging**: HMAC-SHA256 chain-signed tamper-proof logs
- **Supply Chain**: CycloneDX SBOM + hashlock dependency verification
- **OWASP Compliance**: Automated Top-10 API security checks

## Security Audit

We run automated security scans in CI:
- **Bandit**: SAST scanning for Python code
- **pip-audit**: Known vulnerability detection in dependencies
- **safety**: Dependency vulnerability database check

## Dependency Security

All dependencies are verified using hashlock:
```bash
gh-sim hashlock verify
```

## Secure Development Practices

1. All code changes require PR review
2. Pre-commit hooks enforce linting and type checking
3. Secrets are stored via keyring (never in code/env files)
4. Database queries use parameterized statements (SQL injection prevention)
