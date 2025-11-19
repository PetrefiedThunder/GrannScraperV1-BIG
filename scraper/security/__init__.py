"""
GrandmaScrape Security & Authentication System.

Production-grade security features for enterprise deployment.

Features:
- API Key Management (generation, validation, expiration)
- Advanced Rate Limiting (token bucket, per-key, IP-based)
- Request Signing (HMAC-SHA256)
- Security Headers (OWASP compliant)
- CORS Configuration

Usage:
    from scraper.security import APIKeyManager, RateLimiter, RequestSigner

    # API Key management
    key_manager = APIKeyManager()
    api_key = key_manager.generate_key(
        name="production",
        rate_limit=1000,
        allowed_endpoints=["/api/scrape", "/api/analyze"]
    )

    # Rate limiting
    rate_limiter = RateLimiter(requests_per_minute=60)
    allowed = await rate_limiter.check_rate_limit(api_key)

    # Request signing
    signer = RequestSigner(secret_key="your-secret")
    signature = signer.sign_request(method="POST", path="/api/scrape", body=data)
"""

from scraper.security.auth import (
    APIKey,
    APIKeyManager,
    RateLimiter,
    RequestSigner,
    SecurityHeaders,
    CORSConfig
)

__all__ = [
    'APIKey',
    'APIKeyManager',
    'RateLimiter',
    'RequestSigner',
    'SecurityHeaders',
    'CORSConfig'
]
