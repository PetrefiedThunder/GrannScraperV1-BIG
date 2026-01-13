# Dead Code Candidates Analysis

**Generated:** 2026-01-13
**Codebase:** GrannScraperV1-BIG

## Summary

| Category | Count |
|----------|-------|
| Orphan Files (no importers) | 2 |
| Unused Exports | 8 |
| Potentially Dead Functions | 5 |
| Empty `__init__.py` Files | 12 |

---

## Orphan Files

Files with no internal importers (entry points excluded).

### 1. `scraper/monitoring/alerts.py`

| Metric | Value |
|--------|-------|
| **Lines** | 300 |
| **Importers** | 0 (potentially 1) |
| **Status** | SUSPECT |

**Analysis:**
This file defines `AlertManager`, `EmailAlert`, `SlackAlert`, `WebhookAlert` but no other module in the codebase imports them.

**Evidence:**
```bash
$ grep -r "from scraper.monitoring.alerts" scraper/
# No results
$ grep -r "from scraper.monitoring import" scraper/
# No results
```

**Exports:**
```python
# alerts.py
class AlertManager: ...      # Not imported anywhere
class EmailAlert: ...        # Not imported anywhere
class SlackAlert: ...        # Not imported anywhere
class WebhookAlert: ...      # Not imported anywhere
```

**Verdict:** LIKELY DEAD - Feature implemented but not integrated
**Recommendation:**
- Either integrate into `rest_server.py` or `engine.py`
- Or mark as planned feature with TODO comment
- Consider removing if not on roadmap

---

### 2. `scraper/export/cloud_storage.py`

| Metric | Value |
|--------|-------|
| **Lines** | 350 |
| **Importers** | 0 |
| **Status** | SUSPECT |

**Analysis:**
Cloud storage uploaders (S3, GCS, Azure) are defined but not imported by `export_manager.py`.

**Evidence:**
```bash
$ grep -r "cloud_storage" scraper/
# Only finds the file itself
$ grep -r "S3Uploader\|GCSUploader\|AzureUploader" scraper/
# No imports found
```

**Exports:**
```python
# cloud_storage.py
class S3Uploader: ...              # Not imported
class GCSUploader: ...             # Not imported
class AzureUploader: ...           # Not imported
class CloudStorageManager: ...     # Not imported
```

**Verdict:** LIKELY DEAD - Feature implemented but not wired up
**Recommendation:**
- Integrate into `export_manager.py` as export destinations
- Or document as "premium feature" in roadmap

---

## Unused Exports

Functions/classes exported but never imported elsewhere.

### In `scraper/config/models.py`:

```python
# Line 120 - WorkflowStep appears unused outside tests
class WorkflowStep(BaseModel):
    """Workflow step configuration."""
    id: str
    type: str  # scrape, transform, export
    ...
```
**Usage:** Only in `tests/test_models.py` - production code uses `WorkflowNode` from `workflow_dag.py` instead

---

### In `scraper/transforms/cleaning.py`:

```python
# Line 85 - standardize_phone never called
@staticmethod
def standardize_phone(phone: str) -> str:
    """Standardize phone number format."""
    ...
```
**Evidence:** No grep hits in production code, only in test

---

### In `scraper/transforms/type_inference.py`:

```python
# Line 45 - convert_type only used in tests
@staticmethod
def convert_type(value: str, target_type: str) -> Any:
    ...
```

---

### In `scraper/core/fetcher_browser.py`:

```python
# Line 180 - BrowserPool class defined but not used
class BrowserPool:
    """Pool of browser instances for reuse."""
    ...
```
**Analysis:** `BrowserFetcher` creates browsers directly, pool is unused

---

## Empty `__init__.py` Files

These files exist solely for package structure:

| File | Status |
|------|--------|
| `scraper/api/__init__.py` | Empty |
| `scraper/cli/__init__.py` | Empty |
| `scraper/core/__init__.py` | Empty |
| `scraper/export/__init__.py` | Empty |
| `scraper/extractors/__init__.py` | Empty |
| `scraper/ml/__init__.py` | Empty |
| `scraper/monitor/__init__.py` | Empty |
| `scraper/monitoring/__init__.py` | Empty |
| `scraper/observability/__init__.py` | Empty |
| `scraper/scheduler/__init__.py` | Empty |
| `scraper/security/__init__.py` | Empty |
| `scraper/storage/__init__.py` | Empty |
| `scraper/strategies/__init__.py` | Empty |
| `scraper/transforms/__init__.py` | Empty |
| `scraper/ui/__init__.py` | Empty |

**Recommendation:** Consider adding re-exports for cleaner public API:
```python
# scraper/transforms/__init__.py
from .cleaning import DataCleaner
from .type_inference import TypeInferrer
from .deduplication import Deduplicator

__all__ = ["DataCleaner", "TypeInferrer", "Deduplicator"]
```

---

## Potentially Dead Functions

Functions that appear to have no callers.

### 1. `DataCleaner.remove_duplicates()`
**File:** `scraper/transforms/cleaning.py:95`
**Called by:** Only tests
```python
@staticmethod
def remove_duplicates(items: list) -> list:
    """Remove duplicates from list."""
    ...
```

### 2. `SmartCache.get_changes_since()`
**File:** `scraper/storage/smart_cache.py:261`
**Called by:** None
```python
def get_changes_since(self, since: datetime) -> List[Dict]:
    """Get all changes since a given time."""
    ...
```

### 3. `WorkflowDAG.get_execution_plan()`
**File:** `scraper/scheduler/workflow_dag.py:438`
**Called by:** None
```python
def get_execution_plan(self) -> str:
    """Get human-readable execution plan."""
    ...
```

### 4. `PerformanceAnalyzer.display_report()`
**File:** `scraper/monitor/live_dashboard.py:308`
**Called by:** None
```python
def display_report(self, console: Console):
    """Display formatted performance report."""
    ...
```

### 5. `setup_logging_example()` / `setup_security_example()`
**Files:** `observability/logging_system.py:473`, `security/auth.py:496`
**Purpose:** Example/documentation functions
**Recommendation:** Move to examples/ directory or docstrings

---

## Cleanup Recommendations

### Priority 1 - Remove or Integrate
| File | Action |
|------|--------|
| `monitoring/alerts.py` | Integrate or remove |
| `export/cloud_storage.py` | Integrate into export_manager |

### Priority 2 - Clean Up
| Item | Action |
|------|--------|
| `BrowserPool` class | Remove if not needed |
| Example functions | Move to docs/examples |
| Unused test-only methods | Mark with `# pragma: no cover` |

### Priority 3 - Improve
| Item | Action |
|------|--------|
| Empty `__init__.py` | Add public API exports |
| `WorkflowStep` duplication | Remove or consolidate with `WorkflowNode` |

---

## Verification Commands

```bash
# Find unused imports
ruff check scraper/ --select F401

# Find unused functions (requires vulture)
vulture scraper/ --min-confidence 80

# Find unused exports
# Custom script needed - check all __all__ exports against grep

# Check test coverage of "dead" code
pytest --cov=scraper --cov-report=html
# Then check uncovered lines in dead code candidates
```
