# 🔐 Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please email: **security@spectech.pro**

### What to include:
- Type of vulnerability (e.g. XSS, SQL injection, RCE)
- Full paths of source files related to the vulnerability
- Location of the affected source code (tag/branch/commit)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)

### Response Timeline

- **Initial response:** Within 48 hours
- **Assessment:** Within 7 days
- **Resolution:** Within 30 days (critical), 90 days (high/medium)

## Security Best Practices

### For Developers

1. **Never commit secrets** to Git (passwords, API keys, tokens)
2. **Use environment variables** for sensitive data
3. **Enable pre-commit hooks** (detect-secrets, ruff, black)
4. **Run security scans** before pushing:
   ```bash
   ./scripts/security-scan.ps1
