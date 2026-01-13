# Refactoring Priorities - Technical Debt Ranking

**Generated:** 2026-01-13
**Codebase:** GrannScraperV1-BIG

## Executive Summary

| Priority | Count | Estimated Effort |
|----------|-------|------------------|
| P0 - Critical | 1 | Medium |
| P1 - High | 4 | Medium-High |
| P2 - Medium | 6 | Low-Medium |
| P3 - Low | 5 | Low |

---

## P0 - Critical (Fix Now)

### 1. Integrate Orphan Features

**Issue:** Two fully-implemented features (`alerts.py`, `cloud_storage.py`) are not wired into the system.

**Files:**
- `scraper/monitoring/alerts.py` (300 lines)
- `scraper/export/cloud_storage.py` (350 lines)

**Impact:** 650 lines of code providing no value

**Action Items:**
1. **Alerts Integration:**
   ```python
   # In rest_server.py, add:
   from scraper.monitoring.alerts import AlertManager

   alert_manager = AlertManager()

   @app.on_event("startup")
   async def setup_alerts():
       alert_manager.add_channel(SlackAlert(webhook_url=settings.slack_webhook))
   ```

2. **Cloud Storage Integration:**
   ```python
   # In export_manager.py, add:
   from scraper.export.cloud_storage import CloudStorageManager

   def export_to_cloud(self, items, destination: str):
       manager = CloudStorageManager()
       manager.upload(items, destination)
   ```

**Acceptance Criteria:**
- [ ] AlertManager is instantiated and configured on startup
- [ ] Cloud export is available via API endpoint
- [ ] Both features have integration tests

---

## P1 - High (Next Sprint)

### 2. Split God Modules

**Issue:** Several files exceed 500 lines with multiple responsibilities.

#### 2a. Split `rest_server.py` (500 lines)

**Current State:**
```
rest_server.py
├── Job CRUD endpoints (15 endpoints)
├── Workflow endpoints (5 endpoints)
├── Cache endpoints (3 endpoints)
├── Health/Info endpoints (2 endpoints)
└── Background task management
```

**Target State:**
```
api/
├── __init__.py
├── main.py              # FastAPI app factory
├── routers/
│   ├── __init__.py
│   ├── jobs.py          # Job CRUD
│   ├── workflows.py     # Workflow management
│   ├── cache.py         # Cache operations
│   └── health.py        # Health/info
├── dependencies.py      # Shared dependencies
└── middleware.py        # Custom middleware
```

**Evidence:**
```python
# rest_server.py currently has mixed concerns:
@app.post("/api/v1/jobs")         # Line 45
@app.post("/api/v1/workflows")    # Line 180
@app.get("/api/v1/cache/stats")   # Line 250
```

---

#### 2b. Split `data_intelligence.py` (608 lines)

**Current State:**
```
ml/data_intelligence.py
├── DataQualityAnalyzer (200 lines)
├── AnomalyDetector (150 lines)
└── SmartCategorizer (100 lines)
```

**Target State:**
```
ml/
├── __init__.py
├── quality_analyzer.py
├── anomaly_detector.py
└── categorizer.py
```

---

#### 2c. Split `sdk/client.py` (680 lines)

**Current State:** Sync and async clients in one file

**Target State:**
```
sdk/
├── __init__.py
├── base.py           # Shared logic
├── sync_client.py    # GrandmaScrapeClient
└── async_client.py   # AsyncGrandmaScrapeClient
```

---

### 3. Consolidate Duplicate Concepts

**Issue:** `WorkflowStep` (config/models.py) and `WorkflowNode` (scheduler/workflow_dag.py) represent similar concepts.

**Evidence:**
```python
# config/models.py:120
class WorkflowStep(BaseModel):
    id: str
    type: str
    job_id: Optional[str] = None
    depends_on: List[str] = []

# scheduler/workflow_dag.py:33
@dataclass
class WorkflowNode:
    id: str
    type: str
    config: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
```

**Action:** Consolidate into single `WorkflowStep` in `config/models.py`, use throughout.

---

### 4. Fix Export Manager Tight Coupling

**Issue:** `export_manager.py` has hardcoded imports for all exporters.

**Current:**
```python
# export_manager.py:5-10
from scraper.export.csv_exporter import CSVExporter
from scraper.export.json_exporter import JSONExporter
from scraper.export.excel_exporter import ExcelExporter
from scraper.export.sqlite_exporter import SQLiteExporter
from scraper.export.premium_formats import ParquetExporter, XMLExporter
```

**Target:** Registry pattern
```python
# export_manager.py
class ExportManager:
    _exporters: Dict[str, Type[BaseExporter]] = {}

    @classmethod
    def register(cls, format_name: str, exporter_class: Type[BaseExporter]):
        cls._exporters[format_name] = exporter_class

    def get_exporter(self, format_name: str) -> BaseExporter:
        return self._exporters[format_name]()

# Each exporter self-registers:
# csv_exporter.py
ExportManager.register("csv", CSVExporter)
```

---

## P2 - Medium (Backlog - High)

### 5. Add Type Hints to Dynamic Code

**Files Needing Type Improvements:**
| File | Issue |
|------|-------|
| `workflow_dag.py:333` | `_evaluate_condition` uses `Any` extensively |
| `engine.py:150` | `_process_page` returns `Dict[str, Any]` |
| `llm_extractor.py:80` | API response handling lacks types |

**Action:** Add `TypedDict` definitions for structured data.

---

### 6. Replace Bare Except Clauses

**Evidence:**
```python
# ml/data_intelligence.py:203-205
except:
    pass

# strategies/intelligent_extraction.py:344
except:
    suggestions[category] = category
```

**Action:** Replace with specific exception types.

---

### 7. Extract Complex Condition Evaluation

**File:** `scheduler/workflow_dag.py:333-421`

**Issue:** 90-line method for safe condition evaluation

**Action:** Extract to `scraper/utils/safe_eval.py`

---

### 8. Implement Proper Async Context Managers

**Issue:** Several classes with async resources don't implement `__aenter__`/`__aexit__`

**Files:**
- `core/fetcher_browser.py` - BrowserFetcher
- `sdk/client.py` - AsyncGrandmaScrapeClient (partially implemented)

---

### 9. Add Missing `__all__` Exports

**Files:** All `__init__.py` files

**Action:**
```python
# Example for scraper/export/__init__.py
from .base_exporter import BaseExporter
from .csv_exporter import CSVExporter
from .json_exporter import JSONExporter
from .export_manager import ExportManager

__all__ = [
    "BaseExporter",
    "CSVExporter",
    "JSONExporter",
    "ExportManager",
]
```

---

### 10. Remove Example Functions from Production Code

**Files:**
- `observability/logging_system.py:473` - `setup_logging_example()`
- `security/auth.py:496` - `setup_security_example()`

**Action:** Move to `examples/` directory

---

## P3 - Low (Backlog - Low)

### 11. Standardize Logging

**Issue:** Mixed logging patterns across modules

**Evidence:**
```python
# Some files use module-level logger
logger = logging.getLogger(__name__)

# Others create in class
self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
```

**Action:** Standardize on module-level `logger = logging.getLogger(__name__)`

---

### 12. Add Docstrings to Public Methods

**Coverage:** ~60% of public methods have docstrings

**Priority Files:**
- `core/engine.py` - Core class needs complete docs
- `export_manager.py` - Public API needs docs

---

### 13. Consolidate Date/Time Handling

**Issue:** Mixed usage of `datetime.utcnow()` and `datetime.now()`

**Action:** Standardize on `datetime.now(timezone.utc)` (utcnow is deprecated)

---

### 14. Add Input Validation to Public APIs

**Files:** `api/rest_server.py`

**Issue:** Some endpoints lack input validation beyond Pydantic

**Action:** Add explicit validators for URL formats, selector syntax, etc.

---

### 15. Consider Dataclasses for Internal DTOs

**Issue:** Some internal data structures use `Dict[str, Any]` where structured types would be safer

**Example:** `PageResult` in `engine.py` could be a dataclass

---

## Effort Estimates

| ID | Task | Effort | Risk | Value |
|----|------|--------|------|-------|
| 1 | Integrate orphan features | M | L | H |
| 2a | Split rest_server.py | M | M | H |
| 2b | Split data_intelligence.py | S | L | M |
| 2c | Split sdk/client.py | S | L | M |
| 3 | Consolidate WorkflowStep | S | M | M |
| 4 | Registry pattern for exporters | M | M | H |
| 5-15 | Remaining items | S each | L | L-M |

**Legend:** S = Small (<2h), M = Medium (2-8h), L = Large (>8h)

---

## Recommended Sprint Plan

**Sprint N:**
- [ ] P0-1: Integrate alerts.py
- [ ] P0-1: Integrate cloud_storage.py
- [ ] P1-2a: Create API routers structure

**Sprint N+1:**
- [ ] P1-2a: Migrate endpoints to routers
- [ ] P1-3: Consolidate WorkflowStep/WorkflowNode
- [ ] P1-4: Implement exporter registry

**Sprint N+2:**
- [ ] P1-2b: Split data_intelligence.py
- [ ] P1-2c: Split sdk/client.py
- [ ] P2 items as capacity allows
