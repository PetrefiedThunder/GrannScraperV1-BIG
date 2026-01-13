# Circular Dependencies Analysis

**Generated:** 2026-01-13
**Codebase:** GrannScraperV1-BIG

## Summary

| Metric | Count |
|--------|-------|
| Direct Circular Dependencies | 0 |
| Potential Indirect Cycles | 2 |
| Risk Level | LOW |

---

## Direct Circular Dependencies

**None detected.**

The codebase follows a clean layered architecture with no direct circular imports.

---

## Potential Indirect Cycles (N-hop)

### Cycle 1: CLI ↔ API Shared State Risk

**Cycle Path:**
```
scraper/cli/main.py
    → scraper/core/engine.py
    → scraper/core/concurrent_engine.py
        ← scraper/api/rest_server.py
            → scraper/core/engine.py (shared)
```

**Risk:** LOW
**Type:** Shared module dependency (not true circular)

**Evidence:**
```python
# scraper/cli/main.py:16
from scraper.core.engine import ScrapingEngine

# scraper/api/rest_server.py:22
from scraper.core.engine import ScrapingEngine
```

**Analysis:**
Both CLI and API entry points share the same engine module. This is proper shared-library usage, not a circular dependency. However, if engine.py were to import from either CLI or API, it would create a cycle.

**Recommendation:**
- Current design is correct - no action needed
- Maintain discipline: engine should never import from CLI or API layers

---

### Cycle 2: Export Manager ↔ Config Models

**Cycle Path:**
```
scraper/config/models.py (defines ExportConfig)
    ← scraper/export/export_manager.py (imports ExportConfig)
        ← scraper/core/engine.py (imports ExportManager)
            ← scraper/config/models.py (ScrapeJob references export)
```

**Risk:** LOW
**Type:** Data type sharing (intentional coupling)

**Evidence:**
```python
# scraper/config/models.py:85
class ExportConfig(BaseModel):
    formats: List[str] = ["json"]
    output_dir: Optional[str] = None

# scraper/export/export_manager.py:8
from scraper.config.models import ExportConfig
```

**Analysis:**
The `ExportConfig` class is properly defined in the config layer and imported by the export layer. This is correct dependency direction (config → export, not reverse).

**Recommendation:**
- Current design is correct
- Config models should remain the source of truth for all configuration types

---

## Architectural Boundaries

The codebase correctly implements the following layer hierarchy:

```
┌─────────────────────────────────────┐
│  Entry Points (CLI, API)            │  ← Top layer
├─────────────────────────────────────┤
│  Core (Engine, Concurrent Engine)   │
├─────────────────────────────────────┤
│  Services (Export, Transform, ML)   │
├─────────────────────────────────────┤
│  Infrastructure (Fetcher, Cache)    │
├─────────────────────────────────────┤
│  Config (Models, Settings)          │  ← Bottom layer
└─────────────────────────────────────┘
```

**Import Rules (Currently Followed):**
- Upper layers may import from lower layers ✓
- Lower layers MUST NOT import from upper layers ✓
- Same-layer imports should be minimal ✓

---

## Prevention Checklist

To prevent future circular dependencies:

1. [ ] **Never add imports from CLI/API to core modules**
2. [ ] **Keep config/models.py import-free** (only stdlib + pydantic)
3. [ ] **Use dependency injection** for cross-cutting concerns
4. [ ] **Add pre-commit hook** to detect cycles:
   ```bash
   pip install pydeps
   pydeps scraper --no-output --no-show --cluster
   ```

---

## Tool Recommendations

For ongoing monitoring:

```bash
# Check for cycles using pydeps
pydeps scraper --show-cycles --no-output

# Use import-linter for CI/CD
# .importlinter file:
[importlinter]
root_package = scraper

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    scraper.cli
    scraper.api
    scraper.core
    scraper.export
    scraper.config
```
