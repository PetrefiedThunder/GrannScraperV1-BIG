# Refactoring Priorities

**Generated:** 2026-01-13
**Auditor:** Claude Code Dependency Auditor

---

## Priority Matrix

| Priority | Category | Effort | Impact | Risk if Ignored |
|----------|----------|--------|--------|-----------------|
| P0 | Security Integration | Medium | Critical | Security breach |
| P1 | Code Organization | Low | High | Tech debt accumulation |
| P2 | API Structure | Medium | Medium | Maintenance burden |
| P3 | SDK Refactoring | Medium | Low | Developer experience |
| P4 | Feature Integration | High | Medium | Feature waste |

---

## P0: CRITICAL - Security Integration

### Issue: API Running Without Authentication
**File:** `scraper/api/rest_server.py`
**Related:** `scraper/security/auth.py` (orphan)

**Current State:**
```python
# rest_server.py - NO authentication
@app.post("/api/v1/jobs")
async def create_job(job: ScrapeJob):
    # Anyone can create jobs!
```

**Required Changes:**
```python
# rest_server.py - FIXED
from scraper.security.auth import verify_api_key, SecurityHeaders, RateLimiter

# Add security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Add security headers
    response = await call_next(request)
    for key, value in SecurityHeaders.get_headers().items():
        response.headers[key] = value
    return response

# Protected endpoints
@app.post("/api/v1/jobs")
async def create_job(
    job: ScrapeJob,
    api_key: APIKey = Depends(verify_api_key)  # Now protected!
):
    ...
```

**Effort:** 2-4 hours
**Files to Modify:**
- `scraper/api/rest_server.py` (add imports, middleware, Depends)

---

## P1: HIGH - Code Organization

### Issue 1: God Module - `scraper/sdk/client.py` (681 lines)

**Problem:** Sync and async clients duplicate logic

**Current Structure:**
```
sdk/
  client.py (681 lines - sync + async mixed)
```

**Proposed Structure:**
```
sdk/
  __init__.py (exports)
  _base.py (shared logic, ~150 lines)
  sync_client.py (sync implementation, ~200 lines)
  async_client.py (async implementation, ~200 lines)
  models.py (JobStatus, etc., ~50 lines)
```

**Refactoring Steps:**
1. Extract `JobStatus` to `sdk/models.py`
2. Create `sdk/_base.py` with shared URL builders and validation
3. Move `GrandmaScrapeClient` to `sdk/sync_client.py`
4. Move `AsyncGrandmaScrapeClient` to `sdk/async_client.py`
5. Update `sdk/__init__.py` to re-export

**Effort:** 4-6 hours

---

### Issue 2: God Module - `scraper/security/auth.py` (534 lines)

**Problem:** Multiple unrelated security concerns in one file

**Current Structure:**
```
security/
  auth.py (534 lines - API keys, rate limiting, CORS, signing, headers)
```

**Proposed Structure:**
```
security/
  __init__.py
  api_keys.py (APIKey, APIKeyManager, ~100 lines)
  rate_limiting.py (RateLimiter, IPRateLimiter, ~120 lines)
  middleware.py (verify_api_key, security_headers, ~80 lines)
  cors.py (CORSConfig, ~50 lines)
  signing.py (RequestSigner, ~70 lines)
```

**Effort:** 3-4 hours

---

### Issue 3: God Module - `scraper/api/rest_server.py` (450 lines)

**Problem:** All routes in single file

**Proposed Structure:**
```
api/
  __init__.py
  main.py (FastAPI app setup, ~50 lines)
  routes/
    __init__.py
    jobs.py (job CRUD endpoints, ~150 lines)
    cache.py (cache endpoints, ~50 lines)
    quality.py (data quality endpoints, ~50 lines)
    workflows.py (workflow endpoints, ~80 lines)
  dependencies.py (shared Depends, ~30 lines)
```

**Effort:** 4-6 hours

---

## P2: MEDIUM - Structural Improvements

### Issue 4: Reduce `engine.py` Import Count

**Current:** 9 internal imports (highest in codebase)

**Strategy:** Dependency Injection

```python
# Before (tightly coupled)
class ScrapingEngine:
    def __init__(self):
        self.static_fetcher = StaticFetcher()
        self.browser_fetcher = BrowserFetcher()
        self.rate_limiter = RateLimiter()
        # ... 6 more direct instantiations

# After (loosely coupled)
class ScrapingEngine:
    def __init__(
        self,
        fetcher: BaseFetcher,
        extractor: BaseExtractor,
        rate_limiter: RateLimiter,
        export_manager: Optional[ExportManager] = None
    ):
        self.fetcher = fetcher
        self.extractor = extractor
        self.rate_limiter = rate_limiter
        self.export_manager = export_manager

# Factory function for convenience
def create_default_engine():
    return ScrapingEngine(
        fetcher=StaticFetcher(),
        extractor=SelectorExtractor(),
        rate_limiter=RateLimiter(),
    )
```

**Benefits:**
- Easier testing (inject mocks)
- Lower coupling score
- Clearer dependencies
- Plugin architecture ready

**Effort:** 6-8 hours

---

### Issue 5: Missing Base Class - Fetchers

**Current:** `StaticFetcher` and `BrowserFetcher` have no common interface

**Proposed:**
```python
# scraper/core/base_fetcher.py (new file)
from abc import ABC, abstractmethod

class BaseFetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> FetchResult:
        pass

    @abstractmethod
    async def close(self):
        pass

# Update existing fetchers to inherit from BaseFetcher
```

**Effort:** 2-3 hours

---

## P3: LOW - Developer Experience

### Issue 6: Integrate Orphan Utilities

These modules exist but aren't used:

| Module | Integration Point | Effort |
|--------|-------------------|--------|
| `monitoring/alerts.py` | engine.py error handling | 2h |
| `observability/logging_system.py` | All entry points | 3h |
| `monitor/live_dashboard.py` | CLI `--live` flag | 2h |
| `scheduler/advanced_scheduler.py` | New API endpoint | 4h |

---

### Issue 7: Test Coverage Gaps

**Current Coverage Issues:**
- `test_data_intelligence.py` - Tests exist but mock-heavy
- No tests for: `alerts.py`, `logging_system.py`, `auth.py`
- Integration tests missing for full scrape pipeline

**Recommendation:**
```python
# tests/test_integration.py (new)
@pytest.mark.integration
async def test_full_scrape_pipeline():
    """End-to-end test: URL -> Scrape -> Export -> Validate"""
    engine = ScrapingEngine()
    job = ScrapeJob(
        name="integration_test",
        start_url="https://httpbin.org/html",
        ...
    )
    result = await engine.run_job(job)
    assert result.items_scraped > 0
```

**Effort:** 8-12 hours for comprehensive integration tests

---

## P4: FUTURE - Feature Completion

### Issue 8: Premium Features Not Wired

These features are implemented but disconnected:

| Feature | File | Integration Needed |
|---------|------|-------------------|
| Parquet/Avro export | premium_formats.py | ExportManager |
| Cloud storage | cloud_storage.py | Export pipeline |
| Database export | database_connectors.py | Export pipeline |

**Decision Required:** Are these features wanted?
- If YES: Wire into ExportManager (~4h each)
- If NO: Delete files (~30min)

---

## Refactoring Roadmap

### Sprint 1 (URGENT)
- [ ] P0: Integrate security/auth.py into rest_server.py
- [ ] P1: Split sdk/client.py into modules

### Sprint 2 (HIGH)
- [ ] P1: Split rest_server.py into route modules
- [ ] P2: Add dependency injection to engine.py

### Sprint 3 (MEDIUM)
- [ ] P1: Split security/auth.py into focused modules
- [ ] P2: Create BaseFetcher interface
- [ ] P3: Integrate live_dashboard.py into CLI

### Sprint 4 (LOW)
- [ ] P3: Add integration tests
- [ ] P3: Integrate alerts.py into error handling
- [ ] P4: Wire premium export formats (or delete)

---

## Metrics After Refactoring

**Expected Improvements:**

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Max file size | 681 lines | ~200 lines | -71% |
| Orphan modules | 8 | 0-2 | -75%+ |
| engine.py imports | 9 | 3-4 | -56% |
| God modules (>400 lines) | 6 | 0 | -100% |
| Test coverage | ~60% | ~85% | +25% |
| Security vulnerabilities | 1 (no auth) | 0 | -100% |

---

## Quick Wins (< 1 hour each)

1. **Add __all__ to __init__.py files** - Document public API
2. **Add type hints to remaining functions** - IDE support
3. **Add docstrings to exported classes** - Documentation
4. **Create ARCHITECTURE.md** - Onboarding documentation
5. **Add import-linter to CI** - Prevent circular deps
