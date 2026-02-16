"""
Base scraper class that all data source scrapers inherit from.

This ensures consistent interface across all scrapers (Reddit, iFixit, CPSC, etc.)
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
import hashlib


class BaseScraper(ABC):
    """Base class for all data source scrapers."""
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.last_fetch = None
    
    @abstractmethod
    def search_product(self, product_name: str, brand: str = None) -> List[Dict]:
        """
        Search for mentions of a product.
        
        Returns a list of raw data entries:
        [
            {
                "source_url": "https://...",
                "title": "Post/article title",
                "content": "The actual text content",
                "date": "2024-01-15",
                "sentiment": "negative",  # or "positive", "neutral"
                "upvotes": 123,  # engagement metric if available
            }
        ]
        """
        pass
    
    @abstractmethod
    def extract_issues(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Extract specific issues from raw data.
        
        Returns a list of identified issues:
        [
            {
                "title": "Battery swelling after 12 months",
                "description": "Multiple users report...",
                "severity": "high",
                "mention_count": 47,
                "source_urls": ["https://...", "https://..."]
            }
        ]
        """
        pass
    
    @abstractmethod
    def extract_positives(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Extract positive mentions from raw data.
        
        Returns a list of identified positives:
        [
            {
                "title": "Excellent color accuracy",
                "mention_count": 89
            }
        ]
        """
        pass
    
    def generate_issue_id(self, product_id: str, issue_title: str) -> str:
        """Generate a unique ID for an issue."""
        combined = f"{product_id}:{issue_title}".lower()
        return hashlib.md5(combined.encode()).hexdigest()[:12]
    
    def classify_severity(self, issue_text: str, mention_count: int) -> str:
        """
        Classify issue severity based on content and frequency.
        
        Returns: 'critical', 'high', 'medium', or 'low'
        """
        critical_keywords = ['fire', 'burn', 'shock', 'injury', 'dangerous', 'recall', 
                           'safety', 'explode', 'smoke', 'hazard']
        high_keywords = ['dead', 'broken', 'failed', 'defect', 'unusable', 'refund',
                        'warranty', 'replacement', 'DOA', 'return']
        medium_keywords = ['issue', 'problem', 'bug', 'glitch', 'annoying', 'flicker',
                          'noise', 'loud', 'slow']
        
        text_lower = issue_text.lower()
        
        # Check for critical safety issues
        if any(kw in text_lower for kw in critical_keywords):
            return 'critical'
        
        # High severity if defective/broken
        if any(kw in text_lower for kw in high_keywords):
            return 'high'
        
        # Medium if it's a notable problem
        if any(kw in text_lower for kw in medium_keywords):
            return 'medium'
        
        # Also bump severity based on mention count
        if mention_count > 100:
            return 'high'
        elif mention_count > 30:
            return 'medium'
        
        return 'low'
    
    def classify_frequency(self, mention_count: int, total_posts: int) -> str:
        """
        Classify how common an issue is.
        
        Returns: 'very_common', 'common', 'uncommon', or 'rare'
        """
        if total_posts == 0:
            return 'rare'
        
        percentage = (mention_count / total_posts) * 100
        
        if percentage > 25:
            return 'very_common'
        elif percentage > 10:
            return 'common'
        elif percentage > 3:
            return 'uncommon'
        else:
            return 'rare'
    
    def estimate_affected_percentage(self, mention_count: int, total_posts: int) -> float:
        """
        Estimate what percentage of users are affected.
        
        This is a rough estimate - people are more likely to post about problems
        than successes, so we apply a dampening factor.
        """
        if total_posts == 0:
            return 0.0
        
        raw_percentage = (mention_count / total_posts) * 100
        # Dampen because negative posts are over-represented
        dampened = raw_percentage * 0.6
        return round(min(dampened, 50.0), 1)  # Cap at 50%
