"""
Tests for core data models.
"""

import pytest
from scraper.config.models import (
    ScrapeJob,
    FieldConfig,
    FieldType,
    PaginationConfig,
    PaginationMode,
    Workflow,
    WorkflowStep,
)


def test_field_config_basic():
    """Test basic field configuration."""
    field = FieldConfig(
        selector=".title",
        type=FieldType.STRING,
    )

    assert field.selector == ".title"
    assert field.type == FieldType.STRING
    assert field.attr == "text"
    assert not field.use_llm


def test_field_config_llm():
    """Test LLM-enabled field configuration."""
    field = FieldConfig(
        use_llm=True,
        llm_description="Extract the main topic",
        type=FieldType.STRING,
    )

    assert field.use_llm
    assert field.llm_description == "Extract the main topic"


def test_pagination_config_none():
    """Test no pagination."""
    config = PaginationConfig(mode=PaginationMode.NONE)
    assert config.mode == PaginationMode.NONE


def test_pagination_config_url_pattern():
    """Test URL pattern pagination."""
    config = PaginationConfig(
        mode=PaginationMode.URL_PATTERN,
        url_pattern="https://example.com/page/{page}",
        max_pages=10,
    )

    assert config.mode == PaginationMode.URL_PATTERN
    assert "{page}" in config.url_pattern
    assert config.max_pages == 10


def test_pagination_config_next_button():
    """Test next button pagination."""
    config = PaginationConfig(
        mode=PaginationMode.NEXT_BUTTON,
        next_button_selector=".next",
        max_pages=5,
    )

    assert config.mode == PaginationMode.NEXT_BUTTON
    assert config.next_button_selector == ".next"


def test_pagination_validation_next_button_missing_selector():
    """Test that next button mode requires selector."""
    with pytest.raises(ValueError):
        PaginationConfig(
            mode=PaginationMode.NEXT_BUTTON,
            # Missing next_button_selector
        )


def test_scrape_job_minimal():
    """Test minimal scrape job creation."""
    job = ScrapeJob(
        name="test_job",
        start_url="https://example.com",
    )

    assert job.name == "test_job"
    assert job.start_url == "https://example.com"
    assert job.enabled
    assert "example.com" in job.allowed_domains


def test_scrape_job_full():
    """Test full scrape job with all fields."""
    job = ScrapeJob(
        name="full_job",
        start_url="https://example.com",
        description="Test job",
        item_selector=".item",
        fields={
            "title": FieldConfig(selector=".title", type=FieldType.STRING),
            "price": FieldConfig(selector=".price", type=FieldType.CURRENCY),
        },
        pagination=PaginationConfig(
            mode=PaginationMode.URL_PATTERN,
            url_pattern="https://example.com/page/{page}",
            max_pages=5,
        ),
    )

    assert job.name == "full_job"
    assert len(job.fields) == 2
    assert "title" in job.fields
    assert job.pagination.mode == PaginationMode.URL_PATTERN


def test_workflow_simple():
    """Test simple workflow creation."""
    workflow = Workflow(
        name="test_workflow",
        steps=[
            WorkflowStep(id="step1", type="scrape", job_id="job1"),
            WorkflowStep(id="step2", type="export", depends_on=["step1"]),
        ],
    )

    assert workflow.name == "test_workflow"
    assert len(workflow.steps) == 2
    assert workflow.steps[1].depends_on == ["step1"]


def test_workflow_cycle_detection():
    """Test that workflow detects cycles."""
    with pytest.raises(ValueError):
        Workflow(
            name="cyclic",
            steps=[
                WorkflowStep(id="step1", type="scrape", depends_on=["step2"]),
                WorkflowStep(id="step2", type="scrape", depends_on=["step1"]),
            ],
        )
