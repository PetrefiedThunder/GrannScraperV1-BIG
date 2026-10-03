"""Normalize fictional dashboard payloads with the production Pydantic model."""
import json
import sys

from scraper.config.models import ScrapeJob

payload = json.load(sys.stdin)
job = ScrapeJob.model_validate(payload["job"])
# Only return fields under investigation, never default export paths or env values.
print(json.dumps({"max_pages": job.pagination.max_pages, "formats": job.export.formats}))
