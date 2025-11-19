# Contributing to GrandmaScrape

First off, thank you for considering contributing to GrandmaScrape! 🧓✨

It's people like you that make GrandmaScrape the world's most powerful, feature-rich web scraping platform.

## Code of Conduct

This project and everyone participating in it is governed by our commitment to:

- **Be respectful** - Treat everyone with respect and kindness
- **Be collaborative** - Work together to make the project better
- **Be inclusive** - Welcome contributors of all backgrounds and skill levels
- **Be ethical** - Respect websites, follow robots.txt, and scrape responsibly

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

When creating a bug report, include:

- **Clear title and description**
- **Steps to reproduce** the issue
- **Expected behavior** vs **actual behavior**
- **Environment details** (OS, Python version, dependencies)
- **Code samples** or screenshots if applicable
- **Error messages** and stack traces

### Suggesting Features

Feature requests are welcome! Before suggesting a feature:

1. **Check existing issues** to see if it's already proposed
2. **Explain the use case** - why would this feature be useful?
3. **Describe the solution** you'd like to see
4. **Consider alternatives** you've thought about
5. **Note commercial equivalents** if any (helps us stay best-in-class)

### Pull Requests

#### Quick Start for Contributors

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/GrannScraperV1-BIG
cd GrannScraperV1-BIG

# Install dependencies
poetry install
poetry run playwright install chromium

# Create a feature branch
git checkout -b feature/amazing-feature

# Make your changes...

# Run tests
poetry run pytest

# Run linting
poetry run ruff check .
poetry run mypy scraper

# Commit and push
git add .
git commit -m "Add amazing feature"
git push origin feature/amazing-feature

# Open a Pull Request on GitHub
```

#### Pull Request Guidelines

**Before submitting:**

✅ **Code Quality:**
- Follow PEP 8 style guidelines
- Add type hints to all functions
- Write comprehensive docstrings
- Keep functions focused and modular
- Use async/await for I/O operations

✅ **Testing:**
- Add tests for new features
- Ensure all existing tests pass
- Aim for >80% code coverage
- Include both unit and integration tests

✅ **Documentation:**
- Update README.md if adding user-facing features
- Add docstrings to all public APIs
- Update relevant .md files (GETTING_STARTED.md, ULTRA_POWER.md, etc.)
- Add examples if introducing new functionality

✅ **Performance:**
- Profile code for performance bottlenecks
- Use async operations for I/O-bound tasks
- Avoid blocking operations in async contexts
- Consider memory usage for large-scale scraping

✅ **Security:**
- Never commit secrets or API keys
- Validate all user inputs
- Use parameterized queries for databases
- Follow OWASP best practices
- Add security headers where applicable

**PR Template:**

```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran to verify your changes.

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have added type hints
- [ ] I have added tests
- [ ] All tests pass
- [ ] I have updated the documentation
- [ ] I have added examples if needed
```

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Poetry for dependency management
- Git for version control

### Installation

```bash
# Clone the repository
git clone https://github.com/yourorg/GrannScraperV1-BIG
cd GrannScraperV1-BIG

# Install dependencies
poetry install

# Install Playwright browsers
poetry run playwright install chromium

# Verify installation
poetry run pytest
```

### Project Structure

```
GrannScraperV1-BIG/
├── scraper/                    # Main package
│   ├── core/                   # Core scraping engine
│   ├── extractors/             # Data extraction strategies
│   ├── ml/                     # Machine learning features
│   ├── export/                 # Export formats and database connectors
│   ├── monitoring/             # Alerting system
│   ├── security/               # Authentication and security
│   ├── observability/          # Logging and metrics
│   ├── scheduler/              # Job scheduling
│   ├── api/                    # REST API
│   ├── sdk/                    # Python SDK
│   ├── cli/                    # Command-line interface
│   └── web/                    # Web dashboard
├── tests/                      # Test suite
├── benchmarks/                 # Performance benchmarks
├── examples/                   # Example scripts
├── docs/                       # Documentation
└── pyproject.toml              # Dependencies and configuration
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=scraper --cov-report=html

# Run specific test file
poetry run pytest tests/test_scraper.py

# Run with verbose output
poetry run pytest -v
```

### Code Quality Checks

```bash
# Linting with Ruff
poetry run ruff check .

# Type checking with mypy
poetry run mypy scraper

# Format code
poetry run ruff format .
```

## What to Work On

### Good First Issues

Look for issues labeled `good first issue` - these are beginner-friendly tasks.

### Areas That Need Help

**High Priority:**
- 🐛 Bug fixes
- 📚 Documentation improvements
- 🧪 Test coverage
- 🌍 Internationalization (i18n)
- ♿ Accessibility improvements

**Feature Development:**
- 🔌 New export formats
- 🗄️ Additional database connectors
- ☁️ More cloud storage providers
- 📊 Data visualization features
- 🤖 Enhanced ML capabilities

**Infrastructure:**
- 🚀 Performance optimizations
- 🔒 Security enhancements
- 📦 Deployment templates (Kubernetes, Terraform)
- 📈 Monitoring and observability

## Coding Standards

### Python Style

We follow PEP 8 with these specific guidelines:

```python
# Use type hints
async def scrape_url(url: str, max_pages: int = 10) -> List[Dict[str, Any]]:
    """
    Scrape a URL and extract data.

    Args:
        url: The URL to scrape
        max_pages: Maximum number of pages to scrape

    Returns:
        List of extracted data items

    Raises:
        ScrapingError: If scraping fails
    """
    pass

# Use async/await for I/O operations
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# Use context managers
with GrandmaScrapeClient() as client:
    results = client.auto_scrape(url)

# Use descriptive variable names
extracted_items = []  # Good
x = []  # Bad

# Use f-strings for formatting
message = f"Scraped {len(items)} items from {url}"  # Good
message = "Scraped %d items from %s" % (len(items), url)  # Bad
```

### Documentation

```python
# Module docstrings
"""
Module for data extraction strategies.

This module provides various strategies for extracting data from HTML,
including CSS selectors, XPath, and ML-powered semantic extraction.
"""

# Class docstrings
class Scraper:
    """
    Main scraper class for web data extraction.

    Handles HTTP requests, HTML parsing, JavaScript rendering,
    and data extraction using configurable strategies.

    Attributes:
        config: Scraper configuration
        session: HTTP session for requests

    Example:
        >>> scraper = Scraper()
        >>> results = await scraper.scrape("https://example.com")
    """
    pass

# Function docstrings (Google style)
def extract_data(html: str, selector: str) -> List[str]:
    """
    Extract data from HTML using CSS selector.

    Args:
        html: HTML content to parse
        selector: CSS selector for data extraction

    Returns:
        List of extracted text values

    Raises:
        ValueError: If selector is invalid

    Example:
        >>> extract_data("<p>Hello</p>", "p")
        ['Hello']
    """
    pass
```

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```bash
feat(export): add Parquet export format

Implement Parquet export using PyArrow with configurable compression.
Provides 10-100x better compression than CSV while maintaining fast
read performance.

Closes #123
```

```bash
fix(scraper): handle timeout errors gracefully

Add retry logic with exponential backoff for timeout errors.
Prevents job failures on temporary network issues.

Fixes #456
```

## Community

### Where to Get Help

- **GitHub Issues** - For bugs and feature requests
- **GitHub Discussions** - For questions and general discussion
- **Documentation** - Check the comprehensive docs first

### Recognition

Contributors will be recognized in:

- **README.md** - Contributors section
- **Release notes** - Major contributions highlighted
- **CHANGELOG.md** - All contributions documented

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

## Questions?

Don't hesitate to ask! We're here to help:

- Open a GitHub Discussion
- Comment on an existing issue
- Reach out to the maintainers

**Thank you for contributing to GrandmaScrape!** 🧓✨

---

*Making the world's best web scraping platform even better, together.*
