# High-Risk Modules Analysis

**Generated:** 2026-01-13
**Codebase:** GrannScraperV1-BIG

## Risk Classification

| Risk Level | Criteria |
|------------|----------|
| CRITICAL | Coupling > 80, Dependents > 8, Lines > 500 |
| HIGH | Coupling > 60, Dependents > 5, Lines > 400 |
| MEDIUM | Coupling > 40, Dependents > 3, Lines > 300 |
| LOW | Everything else |

---

## CRITICAL Risk Modules (1)

### 1. `scraper/config/models.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 450 |
| **Coupling Score** | 85/100 |
| **Direct Dependents** | 8 |
| **Transitive Dependents** | 15+ |
| **Exports** | 9 classes |
| **Risk Level** | CRITICAL |

**Why Critical:**
This file is the foundational data model layer. ANY change here has cascading effects across the entire codebase.

**Dependents:**
```
scraper/core/engine.py
scraper/core/concurrent_engine.py
scraper/extractors/selector_extractor.py
scraper/export/export_manager.py
scraper/sdk/client.py
scraper/api/rest_server.py
scraper/scheduler/advanced_scheduler.py
tests/test_models.py
tests/test_extractors.py
```

**Blast Radius Calculation:**
```
Direct: 8 files
Indirect (via engine.py): +5 files
Test files affected: 3 files
Total impact: 16 files (30% of codebase)
```

**Key Exports:**
```python
# Lines 25-85 - Core data models
class FieldType(str, Enum): ...      # Used everywhere
class FieldConfig(BaseModel): ...     # Used in 6 files
class PaginationConfig(BaseModel): ...# Used in 4 files
class ScrapeJob(BaseModel): ...       # Used in 8 files
class ScrapeResult(BaseModel): ...    # Used in 5 files
```

**Refactoring Priority:** HIGH
- Consider splitting into separate files: `field_types.py`, `job_config.py`, `pagination.py`
- Use Protocol classes for duck typing where possible
- Add deprecation warnings before changing field names

---

## HIGH Risk Modules (2)

### 2. `scraper/core/engine.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 380 |
| **Coupling Score** | 72/100 |
| **Direct Dependents** | 3 |
| **Imports** | 6 internal modules |
| **Risk Level** | HIGH |

**Why High Risk:**
Central orchestration module. Imports from many modules AND is imported by entry points.

**Import Chain (Afferent):**
```
← scraper/core/concurrent_engine.py
← scraper/api/rest_server.py
← scraper/cli/main.py
```

**Import Chain (Efferent):**
```
→ scraper/config/models.py
→ scraper/extractors/selector_extractor.py
→ scraper/extractors/llm_extractor.py
→ scraper/core/fetcher_static.py
→ scraper/core/fetcher_browser.py
→ scraper/core/rate_limiter.py
```

**Evidence of Coupling:**
```python
# engine.py:12-18
from scraper.config.models import ScrapeJob, ScrapeResult, FieldConfig
from scraper.extractors.selector_extractor import SelectorExtractor
from scraper.extractors.llm_extractor import LLMExtractor
from scraper.core.fetcher_static import StaticFetcher
from scraper.core.fetcher_browser import BrowserFetcher
from scraper.core.rate_limiter import RateLimiter
```

**Refactoring Suggestion:**
- Use dependency injection for fetchers and extractors
- Create abstract factory for extractor selection

---

### 3. `scraper/export/export_manager.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 180 |
| **Coupling Score** | 55/100 |
| **Direct Dependents** | 2 |
| **Imports** | 6 internal modules |
| **Risk Level** | HIGH |

**Why High Risk:**
Central coordinator for all export formats. Changes require testing all export paths.

**Import Chain:**
```
→ scraper/export/csv_exporter.py
→ scraper/export/json_exporter.py
→ scraper/export/excel_exporter.py
→ scraper/export/sqlite_exporter.py
→ scraper/export/premium_formats.py
→ scraper/config/models.py
```

**Refactoring Suggestion:**
- Use plugin/registry pattern instead of direct imports
- Implement lazy loading for premium formats

---

## MEDIUM Risk Modules (4)

### 4. `scraper/api/rest_server.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 500 |
| **Coupling Score** | 45/100 |
| **Risk Level** | MEDIUM |

**Issue:** God module with too many responsibilities
- Job management
- Authentication
- Rate limiting
- Export handling
- Workflow orchestration

**Evidence:**
```python
# rest_server.py - Multiple responsibility areas
@app.post("/api/v1/jobs")           # Job CRUD
@app.post("/api/v1/jobs/{id}/run")  # Execution
@app.get("/api/v1/cache/stats")     # Cache management
@app.post("/api/v1/workflows")      # Workflow management
```

**Refactoring Suggestion:**
- Split into routers: `jobs_router.py`, `workflows_router.py`, `cache_router.py`

---

### 5. `scraper/scheduler/workflow_dag.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 560 |
| **Coupling Score** | 20/100 |
| **Risk Level** | MEDIUM |

**Issue:** Large file with complex logic (DAG validation, execution, condition evaluation)

**Evidence:**
```python
# workflow_dag.py - Complex nested logic
def _evaluate_condition(self, condition: str, context: Dict) -> bool:
    # 80+ lines of AST parsing and safe evaluation
```

**Refactoring Suggestion:**
- Extract `ConditionEvaluator` class
- Extract `DAGValidator` class
- Consider using existing library (networkx) for DAG operations

---

### 6. `scraper/ml/data_intelligence.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 608 |
| **Coupling Score** | 15/100 |
| **Risk Level** | MEDIUM |

**Issue:** Three unrelated classes in one file (DataQualityAnalyzer, AnomalyDetector, SmartCategorizer)

**Refactoring Suggestion:**
- Split into `quality_analyzer.py`, `anomaly_detector.py`, `categorizer.py`

---

### 7. `scraper/sdk/client.py`

| Metric | Value |
|--------|-------|
| **Lines of Code** | 680 |
| **Coupling Score** | 20/100 |
| **Risk Level** | MEDIUM |

**Issue:** Two client implementations in one file (sync + async)

**Refactoring Suggestion:**
- Split into `sync_client.py` and `async_client.py`
- Create shared `base_client.py` for common logic

---

## Blast Radius Summary

```
                    ┌────────────────────────────┐
                    │   scraper/config/models.py │
                    │   BLAST RADIUS: 30%        │
                    │   16 files affected        │
                    └────────────┬───────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ core/engine.py  │   │ export_manager  │   │ sdk/client.py   │
│ BLAST: 15%      │   │ BLAST: 10%      │   │ BLAST: 5%       │
│ 8 files         │   │ 5 files         │   │ 2 files         │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## Recommended Actions

1. **Immediate (This Sprint):**
   - Add comprehensive tests for `config/models.py` (if not exists)
   - Document all public interfaces in high-risk modules

2. **Short-term (Next Sprint):**
   - Split `rest_server.py` into routers
   - Split `data_intelligence.py` into separate files

3. **Long-term (Backlog):**
   - Implement dependency injection in `engine.py`
   - Consider Protocol classes for loose coupling
   - Add architectural fitness functions to CI
