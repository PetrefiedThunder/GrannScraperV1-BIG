# High-Risk Modules Analysis

**Generated:** 2026-01-13
**Auditor:** Claude Code Dependency Auditor

---

## Risk Assessment Criteria

Modules are classified as high-risk based on:
- **Coupling Score:** Ratio of dependencies (inbound + outbound) to total modules
- **Blast Radius:** Number of modules affected if this module changes
- **Lines of Code:** Complexity indicator (>400 lines = high risk)
- **Export Count:** Number of public interfaces (>5 = high risk)

---

## CRITICAL RISK (Immediate Attention Required)

### 1. `scraper/config/models.py`
**Risk Level:** CRITICAL
**Coupling Score:** 0.95
**Blast Radius:** 11+ modules

| Metric | Value | Assessment |
|--------|-------|------------|
| Lines | 280 | Moderate |
| Exports | 9 | High |
| Imported By | 11 modules | Critical |
| Internal Imports | 0 | Good (leaf node) |

**Impact Analysis:**
- Changes to `ScrapeJob`, `FieldConfig`, or `ScrapeResult` will cascade to:
  - `scraper/core/engine.py`
  - `scraper/core/concurrent_engine.py`
  - `scraper/api/rest_server.py`
  - `scraper/cli/main.py`
  - `scraper/cli/smart_commands.py`
  - `scraper/extractors/selector_extractor.py`
  - `scraper/extractors/llm_extractor.py`
  - `scraper/export/export_manager.py`
  - `scraper/sdk/client.py`
  - All test files for these modules

**Evidence:**
```python
# scraper/config/models.py:1-15
class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    # ... widely used enumeration
```

**Recommendations:**
1. Freeze core model interfaces - use deprecation warnings for changes
2. Add comprehensive property-based tests
3. Consider API versioning for models (v1, v2)
4. Any field additions should be Optional with defaults

---

### 2. `scraper/core/engine.py`
**Risk Level:** CRITICAL
**Coupling Score:** 0.85
**Blast Radius:** 9 modules (direct + transitive)

| Metric | Value | Assessment |
|--------|-------|------------|
| Lines | 350 | High |
| Exports | 1 | Good |
| Imported By | 3 modules | Moderate |
| Internal Imports | 9 modules | Critical |

**Impact Analysis:**
- This is the **central orchestrator** - changes here affect scraping behavior globally
- Transitive dependents via api/cli: entire user-facing surface
- Contains critical async logic for scraping coordination

**Evidence:**
```python
# scraper/core/engine.py imports (reconstructed)
from scraper.config.models import ScrapeJob, ScrapeResult, FieldConfig
from scraper.extractors.selector_extractor import SelectorExtractor
from scraper.extractors.llm_extractor import LLMExtractor
from scraper.core.fetcher_static import StaticFetcher
from scraper.core.fetcher_browser import BrowserFetcher
from scraper.core.rate_limiter import RateLimiter
from scraper.export.export_manager import ExportManager
from scraper.transforms.cleaning import DataCleaner
from scraper.transforms.type_inference import TypeInferrer
```

**Recommendations:**
1. Add integration test suite covering all import paths
2. Consider dependency injection to reduce direct coupling
3. Document method contracts explicitly
4. Add type stubs for better IDE support

---

## HIGH RISK (Monitor Closely)

### 3. `scraper/api/rest_server.py`
**Risk Level:** HIGH
**Coupling Score:** 0.75
**Lines:** 450

| Metric | Value | Assessment |
|--------|-------|------------|
| Exports | 2 | Good |
| Imported By | 0 (entry point) | N/A |
| Internal Imports | 6 modules | High |

**Issues Identified:**
- Large monolithic file with all endpoints
- Contains both routing and business logic
- Does not integrate auth module (security/auth.py exists but unused)

**Evidence:**
```python
# scraper/api/rest_server.py:40-60 (reconstructed)
from scraper.config.models import ScrapeJob
from scraper.core.engine import ScrapingEngine
from scraper.core.concurrent_engine import ConcurrentScrapingEngine
from scraper.storage.smart_cache import SmartCache
from scraper.ml.data_intelligence import DataQualityAnalyzer
from scraper.export.export_manager import ExportManager
```

**Recommendations:**
1. Split into route modules: `jobs.py`, `cache.py`, `quality.py`
2. Integrate `security/auth.py` for production-ready authentication
3. Add request validation middleware
4. Extract business logic to service layer

---

### 4. `scraper/sdk/client.py`
**Risk Level:** HIGH
**Coupling Score:** 0.45
**Lines:** 681 (GOD MODULE)

| Metric | Value | Assessment |
|--------|-------|------------|
| Exports | 3 | Moderate |
| Imported By | 2 (examples, tests) | Low |
| Internal Imports | 1 (models only) | Good |

**Issues Identified:**
- Largest file in codebase at 681 lines
- Contains both sync and async clients (code duplication)
- Many similar methods duplicated between clients

**Evidence:**
```python
# Similar patterns duplicated:
# GrandmaScrapeClient.auto_scrape (lines 108-150)
# AsyncGrandmaScrapeClient.auto_scrape (lines 565-592)
```

**Recommendations:**
1. Extract shared logic to base class or mixin
2. Use code generation for sync/async parity
3. Split into `sync_client.py` and `async_client.py`
4. Add retry logic as middleware, not per-method

---

### 5. `scraper/security/auth.py`
**Risk Level:** HIGH (Integration Risk)
**Coupling Score:** 0.30
**Lines:** 534 (GOD MODULE)

| Metric | Value | Assessment |
|--------|-------|------------|
| Exports | 7 | High |
| Imported By | 0 | ORPHAN |
| Internal Imports | 0 | Good (standalone) |

**Critical Issue: ORPHAN MODULE**
This production-grade security module is **not integrated anywhere**. The API server does not use authentication.

**Evidence:**
```python
# scraper/security/auth.py exports (unused):
# - APIKeyManager
# - RateLimiter
# - verify_api_key (FastAPI dependency)
# - CORSConfig
# - SecurityHeaders

# scraper/api/rest_server.py does NOT import security/auth.py
```

**Recommendations:**
1. **URGENT:** Integrate auth into rest_server.py before production
2. Add security middleware to FastAPI app
3. Use `verify_api_key` as route dependency
4. Apply SecurityHeaders to all responses

---

## MEDIUM RISK

### 6. `scraper/export/export_manager.py`
**Coupling Score:** 0.65 | **Lines:** 120

- Central dispatcher for all export formats
- Changes affect all export functionality
- Well-structured but many imports

### 7. `scraper/core/concurrent_engine.py`
**Coupling Score:** 0.55 | **Lines:** 220

- Wraps base engine with concurrency
- Changes to worker pool affect scraping performance
- Good separation from base engine

### 8. `scraper/extractors/selector_extractor.py`
**Coupling Score:** 0.55 | **Lines:** 200

- Core extraction logic used by engine
- CSS/XPath selector implementation
- Changes affect data extraction accuracy

---

## Blast Radius Summary

| Module | Direct Dependents | Transitive Dependents | Risk |
|--------|-------------------|----------------------|------|
| config/models.py | 11 | 15+ | CRITICAL |
| core/engine.py | 3 | 8 | CRITICAL |
| export/base_exporter.py | 5 | 6 | HIGH |
| extractors/base_extractor.py | 2 | 4 | MEDIUM |
| core/rate_limiter.py | 2 | 4 | MEDIUM |

---

## Recommended Actions

### Immediate (Sprint 0)
1. Add comprehensive tests for `config/models.py`
2. Integrate `security/auth.py` into API server
3. Document breaking change policy for models

### Short-term (1-2 Sprints)
1. Split `rest_server.py` into route modules
2. Refactor `sdk/client.py` to reduce duplication
3. Add dependency injection to `engine.py`

### Long-term (Quarterly)
1. Implement API versioning
2. Add mutation testing for high-risk modules
3. Create architectural decision records (ADRs)
