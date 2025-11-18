"""
Advanced extraction strategies with ML-powered pattern recognition.

This module adds intelligent auto-detection of common web patterns
without needing manual selectors.
"""

import logging
from typing import Any, Optional, List, Dict
from collections import Counter

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class IntelligentExtractor:
    """
    ML-inspired pattern recognition for automatic field detection.

    Analyzes page structure to automatically identify:
    - Product listings
    - Article content
    - Pricing information
    - Dates and timestamps
    - Author information
    - Pagination patterns
    """

    def __init__(self):
        self.confidence_threshold = 0.7

    async def auto_detect_item_container(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Automatically detect the container for list items.

        Uses heuristics to find repeating patterns.
        """
        # Find all tags with similar structure
        candidate_containers = []

        # Look for common container patterns
        for tag_name in ['div', 'article', 'li', 'tr']:
            tags = soup.find_all(tag_name)

            # Group by class patterns
            class_groups = {}
            for tag in tags:
                classes = ' '.join(sorted(tag.get('class', [])))
                if classes:
                    if classes not in class_groups:
                        class_groups[classes] = []
                    class_groups[classes].append(tag)

            # Find groups with 3+ items (likely a list)
            for classes, group in class_groups.items():
                if len(group) >= 3:
                    # Check if items have similar structure
                    if self._have_similar_structure(group[:5]):
                        candidate_containers.append({
                            'selector': f"{tag_name}.{classes.split()[0]}" if classes else tag_name,
                            'count': len(group),
                            'confidence': self._calculate_confidence(group)
                        })

        # Return highest confidence container
        if candidate_containers:
            best = max(candidate_containers, key=lambda x: x['confidence'])
            if best['confidence'] > self.confidence_threshold:
                logger.info(f"Auto-detected item container: {best['selector']} ({best['count']} items)")
                return best['selector']

        return None

    def _have_similar_structure(self, tags: List[Tag]) -> bool:
        """Check if tags have similar child structure."""
        if not tags:
            return False

        # Compare child tag patterns
        structures = []
        for tag in tags:
            structure = [child.name for child in tag.children if hasattr(child, 'name')]
            structures.append(tuple(structure))

        # Most common structure should appear in majority
        if structures:
            most_common = Counter(structures).most_common(1)[0]
            similarity = most_common[1] / len(structures)
            return similarity > 0.6

        return False

    def _calculate_confidence(self, group: List[Tag]) -> float:
        """Calculate confidence score for detected pattern."""
        if not group:
            return 0.0

        score = 0.0

        # Similar structure increases confidence
        if self._have_similar_structure(group):
            score += 0.4

        # Consistent text length increases confidence
        text_lengths = [len(tag.get_text(strip=True)) for tag in group]
        if text_lengths:
            avg_length = sum(text_lengths) / len(text_lengths)
            variance = sum((l - avg_length) ** 2 for l in text_lengths) / len(text_lengths)
            if variance < avg_length * 0.5:  # Low variance
                score += 0.3

        # Contains common e-commerce/content indicators
        combined_text = ' '.join(tag.get_text() for tag in group[:3]).lower()
        indicators = ['price', '$', '€', '£', 'buy', 'add to cart', 'read more', 'author', 'posted']
        if any(ind in combined_text for ind in indicators):
            score += 0.3

        return min(score, 1.0)

    async def auto_detect_fields(self, soup: BeautifulSoup, item_selector: str) -> Dict[str, Dict]:
        """
        Automatically detect fields within items.

        Returns suggested field configurations.
        """
        items = soup.select(item_selector)
        if not items or len(items) < 2:
            return {}

        # Analyze first few items to find common patterns
        sample_items = items[:5]

        detected_fields = {}

        # Look for titles (usually largest text element)
        detected_fields.update(self._detect_titles(sample_items))

        # Look for prices
        detected_fields.update(self._detect_prices(sample_items))

        # Look for images
        detected_fields.update(self._detect_images(sample_items))

        # Look for links
        detected_fields.update(self._detect_links(sample_items))

        # Look for dates
        detected_fields.update(self._detect_dates(sample_items))

        # Look for descriptions
        detected_fields.update(self._detect_descriptions(sample_items))

        logger.info(f"Auto-detected {len(detected_fields)} fields")
        return detected_fields

    def _detect_titles(self, items: List[Tag]) -> Dict[str, Dict]:
        """Detect title/heading fields."""
        fields = {}

        for heading_tag in ['h1', 'h2', 'h3', 'h4']:
            headings = [item.find(heading_tag) for item in items]
            headings = [h for h in headings if h]

            if len(headings) >= len(items) * 0.8:  # 80% coverage
                # Try to find common class
                classes = [h.get('class', []) for h in headings]
                common_class = self._find_common_class(classes)

                selector = f"{heading_tag}.{common_class}" if common_class else heading_tag

                fields['title'] = {
                    'selector': selector,
                    'type': 'string',
                    'confidence': len(headings) / len(items),
                    'auto_detected': True
                }
                break

        return fields

    def _detect_prices(self, items: List[Tag]) -> Dict[str, Dict]:
        """Detect price fields."""
        fields = {}

        # Look for common price patterns
        price_patterns = [
            {'class': 'price'},
            {'class': 'cost'},
            {'class': 'amount'},
            {'data-price': True},
        ]

        for pattern in price_patterns:
            prices = []
            for item in items:
                if 'class' in pattern:
                    found = item.find(class_=lambda x: x and pattern['class'] in str(x).lower())
                elif 'data-price' in pattern:
                    found = item.find(attrs={'data-price': True})
                else:
                    found = None

                if found:
                    text = found.get_text(strip=True)
                    # Check if looks like a price
                    if any(symbol in text for symbol in ['$', '€', '£', '¥']) or text.replace('.', '').replace(',', '').isdigit():
                        prices.append(found)

            if len(prices) >= len(items) * 0.7:  # 70% coverage
                # Build selector
                if 'class' in pattern:
                    selector = f".{pattern['class']}"
                else:
                    selector = f"[data-price]"

                fields['price'] = {
                    'selector': selector,
                    'type': 'currency',
                    'confidence': len(prices) / len(items),
                    'auto_detected': True
                }
                break

        return fields

    def _detect_images(self, items: List[Tag]) -> Dict[str, Dict]:
        """Detect image fields."""
        fields = {}

        images = [item.find('img') for item in items]
        images = [img for img in images if img and img.get('src')]

        if len(images) >= len(items) * 0.7:
            # Try to find common class
            classes = [img.get('class', []) for img in images]
            common_class = self._find_common_class(classes)

            selector = f"img.{common_class}" if common_class else "img"

            fields['image'] = {
                'selector': selector,
                'attr': 'src',
                'type': 'url',
                'confidence': len(images) / len(items),
                'auto_detected': True
            }

        return fields

    def _detect_links(self, items: List[Tag]) -> Dict[str, Dict]:
        """Detect link fields."""
        fields = {}

        links = [item.find('a', href=True) for item in items]
        links = [link for link in links if link]

        if len(links) >= len(items) * 0.8:
            classes = [link.get('class', []) for link in links]
            common_class = self._find_common_class(classes)

            selector = f"a.{common_class}" if common_class else "a"

            fields['url'] = {
                'selector': selector,
                'attr': 'href',
                'type': 'url',
                'confidence': len(links) / len(items),
                'auto_detected': True
            }

        return fields

    def _detect_dates(self, items: List[Tag]) -> Dict[str, Dict]:
        """Detect date/time fields."""
        fields = {}

        # Look for <time> tags
        times = [item.find('time') for item in items]
        times = [t for t in times if t]

        if len(times) >= len(items) * 0.7:
            fields['date'] = {
                'selector': 'time',
                'attr': 'datetime',
                'type': 'datetime',
                'confidence': len(times) / len(items),
                'auto_detected': True
            }
        else:
            # Look for common date class patterns
            for date_class in ['date', 'time', 'published', 'timestamp']:
                dates = [item.find(class_=lambda x: x and date_class in str(x).lower()) for item in items]
                dates = [d for d in dates if d]

                if len(dates) >= len(items) * 0.7:
                    fields['date'] = {
                        'selector': f'.{date_class}',
                        'type': 'string',
                        'confidence': len(dates) / len(items),
                        'auto_detected': True
                    }
                    break

        return fields

    def _detect_descriptions(self, items: List[Tag]) -> Dict[str, Dict]:
        """Detect description/content fields."""
        fields = {}

        # Look for paragraph tags or description classes
        for pattern in ['p', '.description', '.summary', '.excerpt']:
            if pattern.startswith('.'):
                class_name = pattern[1:]
                descs = [item.find(class_=lambda x: x and class_name in str(x).lower()) for item in items]
            else:
                descs = [item.find(pattern) for item in items]

            descs = [d for d in descs if d and len(d.get_text(strip=True)) > 20]

            if len(descs) >= len(items) * 0.6:  # 60% coverage
                fields['description'] = {
                    'selector': pattern,
                    'type': 'string',
                    'confidence': len(descs) / len(items),
                    'auto_detected': True
                }
                break

        return fields

    def _find_common_class(self, class_lists: List[List[str]]) -> Optional[str]:
        """Find most common class across elements."""
        if not class_lists:
            return None

        all_classes = []
        for classes in class_lists:
            if classes:
                all_classes.extend(classes)

        if all_classes:
            most_common = Counter(all_classes).most_common(1)[0]
            if most_common[1] >= len(class_lists) * 0.7:  # 70% coverage
                return most_common[0]

        return None


class SmartPaginationDetector:
    """
    Automatically detect pagination patterns.
    """

    async def detect_pagination(self, soup: BeautifulSoup, current_url: str) -> Dict[str, Any]:
        """
        Detect pagination type and configuration.

        Returns pagination config.
        """
        # Look for next button
        next_button = self._find_next_button(soup)
        if next_button:
            return {
                'mode': 'next_button',
                'next_button_selector': self._get_selector_for_element(next_button),
                'confidence': 0.9
            }

        # Look for page number links
        page_links = self._find_page_links(soup, current_url)
        if page_links:
            url_pattern = self._infer_url_pattern(page_links, current_url)
            if url_pattern:
                return {
                    'mode': 'url_pattern',
                    'url_pattern': url_pattern,
                    'confidence': 0.85
                }

        # Check if page has infinite scroll indicators
        if self._has_infinite_scroll_indicators(soup):
            return {
                'mode': 'infinite_scroll',
                'confidence': 0.7
            }

        return {'mode': 'none', 'confidence': 1.0}

    def _find_next_button(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find next page button."""
        # Common patterns for next buttons
        next_patterns = [
            {'text': 'next'},
            {'text': '→'},
            {'text': '>'},
            {'class': 'next'},
            {'class': 'pagination-next'},
            {'rel': 'next'},
        ]

        for pattern in next_patterns:
            if 'text' in pattern:
                found = soup.find('a', string=lambda x: x and pattern['text'] in str(x).lower())
            elif 'class' in pattern:
                found = soup.find('a', class_=lambda x: x and pattern['class'] in str(x).lower())
            elif 'rel' in pattern:
                found = soup.find('a', rel=pattern['rel'])
            else:
                found = None

            if found and found.get('href'):
                return found

        return None

    def _find_page_links(self, soup: BeautifulSoup, current_url: str) -> List[Tag]:
        """Find pagination page number links."""
        # Look for numeric links in pagination areas
        pagination_containers = soup.find_all(['nav', 'div'], class_=lambda x: x and 'pag' in str(x).lower())

        page_links = []
        for container in pagination_containers:
            links = container.find_all('a', href=True)
            for link in links:
                text = link.get_text(strip=True)
                if text.isdigit():
                    page_links.append(link)

        return page_links

    def _infer_url_pattern(self, page_links: List[Tag], current_url: str) -> Optional[str]:
        """Infer URL pattern from page links."""
        if len(page_links) < 2:
            return None

        # Get URLs and page numbers
        url_map = {}
        for link in page_links:
            page_num = link.get_text(strip=True)
            url = link.get('href')
            if page_num.isdigit() and url:
                url_map[int(page_num)] = url

        if len(url_map) < 2:
            return None

        # Try to find pattern
        sorted_pages = sorted(url_map.items())
        url1 = sorted_pages[0][1]
        url2 = sorted_pages[1][1]

        # Simple pattern detection
        if 'page=' in url1 and 'page=' in url2:
            base = url1.split('page=')[0]
            return base + 'page={page}'
        elif '/page/' in url1:
            parts = url1.split('/page/')
            return parts[0] + '/page/{page}'

        return None

    def _has_infinite_scroll_indicators(self, soup: BeautifulSoup) -> bool:
        """Check if page likely uses infinite scroll."""
        # Look for common infinite scroll libraries
        scripts = soup.find_all('script', src=True)
        for script in scripts:
            src = script.get('src', '').lower()
            if any(lib in src for lib in ['infinite-scroll', 'endless-scroll', 'waypoint']):
                return True

        return False

    def _get_selector_for_element(self, element: Tag) -> str:
        """Generate CSS selector for element."""
        classes = element.get('class', [])
        if classes:
            return f"{element.name}.{classes[0]}"

        element_id = element.get('id')
        if element_id:
            return f"#{element_id}"

        return element.name
