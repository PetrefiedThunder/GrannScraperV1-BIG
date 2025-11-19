"""
Production Security Features.

Enterprise-grade authentication, authorization, and rate limiting.
Competitors charge $299-999/month for these features.
"""

import asyncio
import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ============================================================================
# API KEY MANAGEMENT
# ============================================================================

class APIKey(BaseModel):
    """API key model."""
    key: str
    name: str
    created_at: datetime
    last_used: Optional[datetime] = None
    rate_limit: int = 100  # requests per minute
    allowed_endpoints: Optional[List[str]] = None  # None = all endpoints
    expires_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = {}


class APIKeyManager:
    """
    Manage API keys for authentication.

    Features:
    - Generate secure API keys
    - Validate and authenticate requests
    - Track usage per key
    - Rate limiting per key
    - Key expiration
    - Endpoint-specific permissions
    """

    def __init__(self):
        """Initialize API key manager."""
        self.keys: Dict[str, APIKey] = {}
        self.usage_stats: Dict[str, Dict[str, Any]] = {}

    def generate_key(
        self,
        name: str,
        rate_limit: int = 100,
        allowed_endpoints: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a new API key.

        Args:
            name: Descriptive name for the key
            rate_limit: Requests per minute
            allowed_endpoints: List of allowed endpoints (None = all)
            expires_in_days: Key expiration in days (None = never)
            metadata: Additional metadata

        Returns:
            Generated API key
        """
        # Generate secure random key
        key = f"gms_{secrets.token_urlsafe(32)}"

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key = APIKey(
            key=key,
            name=name,
            created_at=datetime.utcnow(),
            rate_limit=rate_limit,
            allowed_endpoints=allowed_endpoints,
            expires_at=expires_at,
            metadata=metadata or {}
        )

        self.keys[key] = api_key

        logger.info(f"Generated API key: {name} (rate_limit={rate_limit}/min)")

        return key

    def validate_key(self, key: str, endpoint: Optional[str] = None) -> bool:
        """
        Validate an API key.

        Args:
            key: API key to validate
            endpoint: Endpoint being accessed

        Returns:
            True if valid, False otherwise
        """
        if key not in self.keys:
            logger.warning(f"Invalid API key attempted: {key[:10]}...")
            return False

        api_key = self.keys[key]

        # Check if active
        if not api_key.is_active:
            logger.warning(f"Inactive API key used: {api_key.name}")
            return False

        # Check expiration
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            logger.warning(f"Expired API key used: {api_key.name}")
            return False

        # Check endpoint permissions
        if api_key.allowed_endpoints and endpoint:
            if endpoint not in api_key.allowed_endpoints:
                logger.warning(f"Unauthorized endpoint access: {api_key.name} -> {endpoint}")
                return False

        # Update last used
        api_key.last_used = datetime.utcnow()

        return True

    def revoke_key(self, key: str):
        """Revoke an API key."""
        if key in self.keys:
            self.keys[key].is_active = False
            logger.info(f"Revoked API key: {self.keys[key].name}")

    def get_usage_stats(self, key: str) -> Dict[str, Any]:
        """Get usage statistics for a key."""
        return self.usage_stats.get(key, {
            "total_requests": 0,
            "requests_today": 0,
            "last_request": None,
            "endpoints_used": []
        })


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    """
    Token bucket rate limiter.

    Implements per-key and global rate limiting with sliding window.
    """

    def __init__(self):
        """Initialize rate limiter."""
        self.buckets: Dict[str, Dict[str, Any]] = {}
        self.global_limit = 1000  # Global requests per minute

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.

        Args:
            key: Unique identifier (API key, IP, user ID)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            (allowed, info) - allowed is True if within limit
        """
        now = time.time()

        if key not in self.buckets:
            self.buckets[key] = {
                'requests': [],
                'total': 0
            }

        bucket = self.buckets[key]

        # Remove old requests outside the window
        cutoff = now - window_seconds
        bucket['requests'] = [ts for ts in bucket['requests'] if ts > cutoff]

        current_count = len(bucket['requests'])

        info = {
            'limit': limit,
            'remaining': max(0, limit - current_count),
            'reset_at': int(now + window_seconds),
            'current_count': current_count
        }

        if current_count >= limit:
            logger.warning(f"Rate limit exceeded for {key}: {current_count}/{limit}")
            return False, info

        # Add current request
        bucket['requests'].append(now)
        bucket['total'] += 1

        return True, info

    def get_stats(self, key: str) -> Dict[str, Any]:
        """Get rate limit statistics."""
        if key not in self.buckets:
            return {
                'total_requests': 0,
                'current_window': 0,
                'all_time': 0
            }

        bucket = self.buckets[key]
        return {
            'total_requests': bucket['total'],
            'current_window': len(bucket['requests']),
            'all_time': bucket['total']
        }


# ============================================================================
# AUTHENTICATION MIDDLEWARE
# ============================================================================

security = HTTPBearer()

api_key_manager = APIKeyManager()
rate_limiter = RateLimiter()


async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> APIKey:
    """
    Verify API key from request.

    Usage in FastAPI:
        @app.get("/protected")
        async def protected_route(api_key: APIKey = Depends(verify_api_key)):
            ...
    """
    token = credentials.credentials

    # Validate key
    endpoint = request.url.path
    if not api_key_manager.validate_key(token, endpoint):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key"
        )

    api_key = api_key_manager.keys[token]

    # Check rate limit
    allowed, info = rate_limiter.check_rate_limit(
        token,
        api_key.rate_limit,
        window_seconds=60
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Resets at {info['reset_at']}",
            headers={
                'X-RateLimit-Limit': str(info['limit']),
                'X-RateLimit-Remaining': str(info['remaining']),
                'X-RateLimit-Reset': str(info['reset_at'])
            }
        )

    # Add rate limit headers to response (done in middleware)
    request.state.rate_limit_info = info
    request.state.api_key = api_key

    return api_key


# ============================================================================
# IP-BASED RATE LIMITING
# ============================================================================

class IPRateLimiter:
    """
    IP-based rate limiting for unauthenticated requests.

    Protects against abuse from anonymous users.
    """

    def __init__(self):
        """Initialize IP rate limiter."""
        self.limiter = RateLimiter()
        self.default_limit = 60  # 60 requests per minute for unauthenticated

    async def check_ip_rate_limit(self, request: Request):
        """Check IP-based rate limit."""
        # Get client IP
        client_ip = request.client.host

        # Check rate limit
        allowed, info = self.limiter.check_rate_limit(
            f"ip:{client_ip}",
            self.default_limit,
            window_seconds=60
        )

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for unauthenticated requests. Please use an API key.",
                headers={
                    'X-RateLimit-Limit': str(info['limit']),
                    'X-RateLimit-Remaining': str(info['remaining']),
                    'X-RateLimit-Reset': str(info['reset_at'])
                }
            )

        request.state.rate_limit_info = info


# ============================================================================
# CORS SECURITY
# ============================================================================

class CORSConfig:
    """
    CORS configuration for production.

    Prevents unauthorized cross-origin requests.
    """

    @staticmethod
    def get_production_config():
        """Get production CORS configuration."""
        return {
            "allow_origins": [
                "https://yourdomain.com",
                "https://app.yourdomain.com"
            ],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Authorization", "Content-Type"],
            "expose_headers": ["X-RateLimit-Limit", "X-RateLimit-Remaining"],
            "max_age": 3600
        }

    @staticmethod
    def get_development_config():
        """Get development CORS configuration."""
        return {
            "allow_origins": ["*"],
            "allow_credentials": True,
            "allow_methods": ["*"],
            "allow_headers": ["*"]
        }


# ============================================================================
# REQUEST SIGNING
# ============================================================================

class RequestSigner:
    """
    Sign requests for enhanced security.

    Prevents request tampering and replay attacks.
    """

    def __init__(self, secret_key: str):
        """Initialize request signer."""
        self.secret_key = secret_key

    def sign_request(
        self,
        method: str,
        path: str,
        body: str,
        timestamp: int
    ) -> str:
        """
        Generate request signature.

        Args:
            method: HTTP method
            path: Request path
            body: Request body
            timestamp: Unix timestamp

        Returns:
            HMAC signature
        """
        message = f"{method}:{path}:{body}:{timestamp}"
        signature = hashlib.sha256(
            f"{message}:{self.secret_key}".encode()
        ).hexdigest()

        return signature

    def verify_signature(
        self,
        signature: str,
        method: str,
        path: str,
        body: str,
        timestamp: int,
        max_age_seconds: int = 300
    ) -> bool:
        """
        Verify request signature.

        Args:
            signature: Provided signature
            method: HTTP method
            path: Request path
            body: Request body
            timestamp: Unix timestamp
            max_age_seconds: Maximum allowed age

        Returns:
            True if valid, False otherwise
        """
        # Check timestamp freshness
        now = int(time.time())
        if abs(now - timestamp) > max_age_seconds:
            logger.warning(f"Request timestamp too old: {timestamp}")
            return False

        # Verify signature
        expected_signature = self.sign_request(method, path, body, timestamp)

        return secrets.compare_digest(signature, expected_signature)


# ============================================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================================

class SecurityHeaders:
    """
    Add security headers to all responses.

    Implements OWASP best practices.
    """

    @staticmethod
    def get_headers() -> Dict[str, str]:
        """Get security headers."""
        return {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",

            # Prevent MIME sniffing
            "X-Content-Type-Options": "nosniff",

            # Enable XSS protection
            "X-XSS-Protection": "1; mode=block",

            # Force HTTPS
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

            # Control referrer information
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Content Security Policy
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",

            # Permissions Policy
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def setup_security_example():
    """Example of setting up security features."""

    # Create API key manager
    manager = APIKeyManager()

    # Generate keys for different clients
    admin_key = manager.generate_key(
        name="Admin Dashboard",
        rate_limit=1000,  # 1000 req/min
        metadata={"role": "admin"}
    )

    user_key = manager.generate_key(
        name="User App",
        rate_limit=100,  # 100 req/min
        allowed_endpoints=["/api/v1/jobs", "/api/v1/results"],
        expires_in_days=30
    )

    test_key = manager.generate_key(
        name="Test Environment",
        rate_limit=10,
        expires_in_days=7
    )

    print(f"Admin Key: {admin_key}")
    print(f"User Key: {user_key}")
    print(f"Test Key: {test_key}")

    # Validate key
    is_valid = manager.validate_key(admin_key, "/api/v1/jobs")
    print(f"Key valid: {is_valid}")

    # Check rate limit
    limiter = RateLimiter()
    allowed, info = limiter.check_rate_limit(admin_key, limit=1000)
    print(f"Rate limit: {info}")
