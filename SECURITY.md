# Security Policy

## Supported Versions

We take security seriously. The following versions of GrandmaScrape are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Features

GrandmaScrape includes enterprise-grade security features out of the box:

### Authentication & Authorization
- ✅ API Key Management (generation, validation, expiration)
- ✅ Endpoint-specific permissions
- ✅ Key rotation support

### Rate Limiting & Protection
- ✅ Token bucket algorithm
- ✅ Per-key rate limiting
- ✅ IP-based rate limiting
- ✅ Sliding window implementation

### Request Security
- ✅ HMAC-SHA256 request signing
- ✅ Replay attack prevention
- ✅ Timestamp validation

### HTTP Security Headers (OWASP Compliant)
- ✅ X-Frame-Options (clickjacking protection)
- ✅ X-Content-Type-Options (MIME sniffing prevention)
- ✅ X-XSS-Protection
- ✅ Strict-Transport-Security (HSTS)
- ✅ Content-Security-Policy

### Data Protection
- ✅ Environment variable configuration (no hardcoded secrets)
- ✅ Secure key generation using `secrets` module
- ✅ Encrypted cloud storage uploads (S3, GCS, Azure)

### Audit & Compliance
- ✅ Audit logging for security events
- ✅ SOC 2 ready
- ✅ GDPR ready (data retention controls)

## Reporting a Vulnerability

We take all security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 1. **DO NOT** Open a Public Issue

Please **do not** report security vulnerabilities through public GitHub issues. This could put users at risk.

### 2. Report Privately

**Email:** security@grandmascrape.io (if available)

**GitHub Security Advisory:** Use GitHub's private vulnerability reporting feature:
1. Go to the repository's "Security" tab
2. Click "Report a vulnerability"
3. Fill in the details

### 3. Include These Details

Please provide as much information as possible:

- **Type of vulnerability** (e.g., XSS, SQL injection, authentication bypass)
- **Full path** of affected source file(s)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept** or exploit code (if possible)
- **Impact** of the vulnerability
- **Suggested fix** (if you have one)

**Example Report:**

```
Subject: [SECURITY] API Key Bypass Vulnerability

Type: Authentication Bypass
Severity: High
Affected File: scraper/security/auth.py:123

Description:
API key validation can be bypassed by sending a specially crafted header...

Steps to Reproduce:
1. Send request to /api/scrape
2. Add header: X-API-Key: [malformed key]
3. Request is processed without authentication

Impact:
Unauthenticated users can access protected endpoints

Suggested Fix:
Add input validation before regex matching...
```

### 4. What to Expect

- **Acknowledgment:** Within 48 hours
- **Assessment:** Within 5 business days
- **Fix timeline:** Depends on severity
  - Critical: 24-48 hours
  - High: 1 week
  - Medium: 2 weeks
  - Low: 30 days
- **Public disclosure:** After fix is released (coordinated disclosure)

### 5. Responsible Disclosure

We follow responsible disclosure principles:

1. **Reporter notifies us** privately
2. **We acknowledge** within 48 hours
3. **We work on a fix** (keep reporter updated)
4. **We release the fix** (with security advisory)
5. **Public disclosure** (credit to reporter if desired)

**Please give us reasonable time to fix the issue before public disclosure.**

## Security Best Practices for Users

### API Key Security

```bash
# ✅ Good - Use environment variables
export GRANDMA_API_KEY="gms_your_secret_key"
scraper serve

# ❌ Bad - Never hardcode keys
api_key = "gms_your_secret_key"  # Don't do this!
```

### Configuration Security

```python
# ✅ Good - Use pydantic-settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str
    database_url: str

    class Config:
        env_file = ".env"

# ❌ Bad - Hardcoded secrets
API_KEY = "hardcoded_secret"
```

### Database Connections

```python
# ✅ Good - Use parameterized queries (we handle this)
await connector.insert("users", [{"name": user_input}])

# ❌ Bad - String concatenation (we prevent this)
# query = f"INSERT INTO users VALUES ('{user_input}')"  # SQL injection risk!
```

### Cloud Storage

```python
# ✅ Good - Use encryption
await s3.upload_file(
    path,
    encryption="AES256",
    public=False
)

# ❌ Bad - Public, unencrypted
await s3.upload_file(path, public=True)
```

### Web Dashboard

```bash
# ✅ Good - Bind to localhost in production
scraper serve --host 127.0.0.1 --port 8000

# ❌ Bad - Public access without authentication
scraper serve --host 0.0.0.0  # Only behind firewall/VPN!
```

### Rate Limiting

```python
# ✅ Good - Respect rate limits
config = ScraperConfig(
    rate_limit=1,  # 1 request/second
    respect_robots_txt=True
)

# ❌ Bad - Aggressive scraping
config = ScraperConfig(rate_limit=100)  # May get blocked!
```

## Security Checklist for Deployment

Before deploying GrandmaScrape in production:

### Infrastructure
- [ ] Use HTTPS/TLS for all API endpoints
- [ ] Configure firewall rules (allow only necessary ports)
- [ ] Use VPN or IP whitelist for admin access
- [ ] Enable cloud provider security features (AWS Security Groups, etc.)

### Application
- [ ] Generate unique API keys for each user/service
- [ ] Set appropriate rate limits
- [ ] Enable request signing for sensitive operations
- [ ] Configure CORS appropriately (don't use "*")
- [ ] Review security headers configuration

### Data
- [ ] Use environment variables for secrets (never commit .env files)
- [ ] Enable encryption for cloud storage
- [ ] Use database connection pooling with SSL
- [ ] Implement data retention policies
- [ ] Regular backups with encryption

### Monitoring
- [ ] Enable audit logging
- [ ] Set up alerting for security events
- [ ] Monitor rate limit violations
- [ ] Track failed authentication attempts
- [ ] Review logs regularly

### Updates
- [ ] Keep dependencies updated (run `poetry update` regularly)
- [ ] Subscribe to security advisories
- [ ] Have an incident response plan
- [ ] Test disaster recovery procedures

## Known Security Considerations

### Scraping Ethics
- GrandmaScrape respects `robots.txt` by default
- Rate limiting prevents accidental DDoS
- No anti-detection features (transparent operation)
- **User responsibility:** Ensure you have permission to scrape target sites

### Third-Party Dependencies
- We use well-maintained, security-audited libraries
- Dependencies are regularly updated
- Run `poetry show --outdated` to check for updates
- Security advisories are monitored via GitHub Dependabot

### Cloud Credentials
- AWS, GCP, Azure credentials are never stored in code
- Use IAM roles and service accounts with minimal permissions
- Rotate credentials regularly
- Consider using secret management services (AWS Secrets Manager, etc.)

## Security Updates

Security updates will be released as:

1. **Patch versions** (0.1.x) for minor security fixes
2. **Minor versions** (0.x.0) for security enhancements
3. **Security advisories** published on GitHub

**Subscribe to updates:**
- Watch the GitHub repository
- Enable GitHub security alerts
- Check CHANGELOG.md regularly

## Bug Bounty Program

We currently do not have a formal bug bounty program, but we deeply appreciate security researchers who help keep GrandmaScrape secure.

**Recognition:**
- Credit in security advisory (if desired)
- Acknowledgment in CHANGELOG.md
- Contributor status

## Contact

For security-related questions or concerns:

- **Security issues:** Use GitHub Security Advisory (preferred)
- **General security questions:** Open a GitHub Discussion
- **Urgent issues:** Tag with `security` label

## Compliance

GrandmaScrape is designed to support compliance with:

- **SOC 2** - Audit logging, access controls
- **GDPR** - Data retention, right to erasure
- **CCPA** - Data privacy controls
- **PCI DSS** - Secure data handling (if processing payment data)

**Note:** Compliance is a shared responsibility. GrandmaScrape provides the tools, but you must configure and use them appropriately for your use case.

## Security Roadmap

Planned security enhancements:

- [ ] OAuth 2.0 / OpenID Connect support
- [ ] Multi-factor authentication (MFA)
- [ ] Role-based access control (RBAC)
- [ ] Secrets management integration (Vault, AWS Secrets Manager)
- [ ] Automated security scanning (SAST/DAST)
- [ ] Penetration testing
- [ ] SOC 2 Type II certification
- [ ] Formal bug bounty program

---

**Thank you for helping keep GrandmaScrape and our users secure!** 🔒

*Last updated: 2025-11-19*
