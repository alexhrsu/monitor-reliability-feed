"""
Reddit Scraper

This file has two implementations:
1. MockRedditScraper - Uses realistic sample data (for development/demo)
2. RedditScraper - Uses real Reddit API (requires credentials)

We'll use the mock version until your Reddit API access is approved,
then swap to the real one.
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import random
import re

import sys
sys.path.append(str(__file__).rsplit('/', 1)[0])
from base import BaseScraper


class MockRedditScraper(BaseScraper):
    """
    Mock Reddit scraper with realistic sample data.
    
    This generates realistic-looking data based on known monitor issues
    so we can develop and demo without waiting for API approval.
    """
    
    # Real issues that exist for various monitors (from research)
    KNOWN_ISSUES = {
        "samsung-odyssey-g9": [
            {"title": "Flickering at 240Hz", "severity": "high", "mentions": 342, "affected": 23},
            {"title": "Dead pixels on delivery", "severity": "medium", "mentions": 89, "affected": 8},
            {"title": "Scan lines in dark scenes", "severity": "medium", "mentions": 156, "affected": 15},
            {"title": "G-Sync compatibility issues", "severity": "medium", "mentions": 78, "affected": 7},
        ],
        "lg-27gp950": [
            {"title": "IPS glow in corners", "severity": "low", "mentions": 234, "affected": 35},
            {"title": "Firmware update bricks monitor", "severity": "critical", "mentions": 45, "affected": 3},
            {"title": "HDR washed out colors", "severity": "medium", "mentions": 123, "affected": 18},
        ],
        "asus-pg42uq": [
            {"title": "OLED burn-in concerns", "severity": "medium", "mentions": 567, "affected": 12},
            {"title": "Loud fan noise", "severity": "low", "mentions": 89, "affected": 20},
            {"title": "ABL too aggressive", "severity": "medium", "mentions": 234, "affected": 25},
        ],
        "dell-aw3423dwf": [
            {"title": "QD-OLED text fringing", "severity": "low", "mentions": 445, "affected": 40},
            {"title": "Scan lines visible in content", "severity": "medium", "mentions": 123, "affected": 10},
            {"title": "VRR flicker in some games", "severity": "medium", "mentions": 167, "affected": 15},
        ],
        "gigabyte-m32u": [
            {"title": "Terrible QC - dead pixels common", "severity": "high", "mentions": 289, "affected": 25},
            {"title": "Backlight bleed", "severity": "medium", "mentions": 345, "affected": 30},
            {"title": "Joystick stops working", "severity": "medium", "mentions": 78, "affected": 8},
        ],
    }
    
    KNOWN_POSITIVES = {
        "samsung-odyssey-g9": [
            {"title": "Incredible immersion", "mentions": 891},
            {"title": "Great for productivity", "mentions": 567},
        ],
        "lg-27gp950": [
            {"title": "Excellent color accuracy", "mentions": 445},
            {"title": "Great HDR implementation", "mentions": 334},
        ],
        "asus-pg42uq": [
            {"title": "Perfect blacks", "mentions": 1203},
            {"title": "Best gaming monitor available", "mentions": 892},
        ],
        "dell-aw3423dwf": [
            {"title": "Best value OLED", "mentions": 1567},
            {"title": "Stunning colors", "mentions": 934},
        ],
        "gigabyte-m32u": [
            {"title": "Great value for 4K 144Hz", "mentions": 456},
            {"title": "Solid build quality", "mentions": 234},
        ],
    }
    
    def __init__(self):
        super().__init__("reddit_mock")
        self.subreddits = ["monitors", "ultrawidemasterrace", "buildapc", "hardware"]
    
    def search_product(self, product_name: str, brand: str = None) -> List[Dict]:
        """Generate realistic Reddit-like data for a product."""
        
        # Create a product key for lookup
        product_key = self._normalize_product_name(product_name, brand)
        
        results = []
        base_date = datetime.utcnow() - timedelta(days=180)
        
        # Generate some realistic posts
        num_posts = random.randint(50, 200)
        
        for i in range(num_posts):
            post_date = base_date + timedelta(days=random.randint(0, 180))
            sentiment = random.choices(
                ["positive", "negative", "neutral"],
                weights=[0.4, 0.35, 0.25]
            )[0]
            
            results.append({
                "source_url": f"https://reddit.com/r/{random.choice(self.subreddits)}/comments/{i:06x}",
                "title": self._generate_post_title(product_name, sentiment),
                "content": self._generate_post_content(product_key, sentiment),
                "date": post_date.isoformat(),
                "sentiment": sentiment,
                "upvotes": random.randint(1, 500) if sentiment != "neutral" else random.randint(1, 50),
                "subreddit": random.choice(self.subreddits),
                "comment_count": random.randint(5, 150),
            })
        
        self.last_fetch = datetime.utcnow()
        return results
    
    def _normalize_product_name(self, product_name: str, brand: str = None) -> str:
        """Normalize product name to match our known issues database."""
        name = product_name.lower()
        if brand:
            name = f"{brand.lower()}-{name}"
        
        # Try to match known products
        for key in self.KNOWN_ISSUES.keys():
            if key in name.replace(" ", "-") or name.replace(" ", "-") in key:
                return key
        
        # Return normalized version
        return name.replace(" ", "-")
    
    def _generate_post_title(self, product_name: str, sentiment: str) -> str:
        """Generate a realistic Reddit post title."""
        positive_titles = [
            f"Just got my {product_name} - it's amazing!",
            f"{product_name} review after 3 months - still love it",
            f"Finally upgraded to {product_name}, no regrets",
            f"{product_name} is worth every penny",
        ]
        negative_titles = [
            f"{product_name} issues - anyone else experiencing this?",
            f"Disappointed with my {product_name}",
            f"Warning: {product_name} quality control issues",
            f"Returning my {product_name} - here's why",
            f"{product_name} problems megathread",
        ]
        neutral_titles = [
            f"Question about {product_name}",
            f"{product_name} vs competitors?",
            f"Thinking about getting {product_name}",
            f"{product_name} settings recommendations?",
        ]
        
        if sentiment == "positive":
            return random.choice(positive_titles)
        elif sentiment == "negative":
            return random.choice(negative_titles)
        else:
            return random.choice(neutral_titles)
    
    def _generate_post_content(self, product_key: str, sentiment: str) -> str:
        """Generate realistic post content."""
        if sentiment == "negative" and product_key in self.KNOWN_ISSUES:
            issue = random.choice(self.KNOWN_ISSUES[product_key])
            return f"Has anyone else experienced {issue['title'].lower()}? I've had my monitor for a few months and this is really frustrating. Thinking about returning it."
        elif sentiment == "positive" and product_key in self.KNOWN_POSITIVES:
            positive = random.choice(self.KNOWN_POSITIVES[product_key])
            return f"Absolutely loving my new monitor. {positive['title']}. Best purchase I've made this year."
        else:
            return "Looking for opinions on this monitor. Worth the price?"
    
    def extract_issues(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract issues from the mock data."""
        # Count negative sentiments and extract issue patterns
        negative_posts = [p for p in raw_data if p.get('sentiment') == 'negative']
        total_posts = len(raw_data)
        
        if not negative_posts:
            return []
        
        # Try to identify the product and return known issues
        # In real implementation, we'd use NLP to extract issues from text
        
        issues = []
        seen_issues = set()
        
        for post in negative_posts:
            content = post.get('content', '').lower()
            
            # Check for known issue patterns
            issue_patterns = [
                ("flicker", "Flickering issues reported"),
                ("dead pixel", "Dead pixels on delivery"),
                ("backlight bleed", "Backlight bleed issues"),
                ("burn-in", "OLED burn-in concerns"),
                ("scan line", "Visible scan lines"),
                ("quality control", "Quality control problems"),
                ("defect", "Manufacturing defects reported"),
            ]
            
            for pattern, title in issue_patterns:
                if pattern in content and title not in seen_issues:
                    seen_issues.add(title)
                    mention_count = sum(1 for p in negative_posts if pattern in p.get('content', '').lower())
                    
                    issues.append({
                        "title": title,
                        "description": f"Multiple users reporting {pattern} issues",
                        "severity": self.classify_severity(title, mention_count),
                        "frequency": self.classify_frequency(mention_count, total_posts),
                        "mention_count": mention_count,
                        "affected_percentage": self.estimate_affected_percentage(mention_count, total_posts),
                        "source_urls": [p['source_url'] for p in negative_posts if pattern in p.get('content', '').lower()][:5],
                        "first_reported": min(p['date'] for p in negative_posts if pattern in p.get('content', '').lower()),
                        "status": "ongoing"
                    })
        
        return sorted(issues, key=lambda x: x['mention_count'], reverse=True)
    
    def extract_positives(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract positives from the mock data."""
        positive_posts = [p for p in raw_data if p.get('sentiment') == 'positive']
        
        if not positive_posts:
            return []
        
        positives = []
        seen = set()
        
        positive_patterns = [
            ("amazing", "Highly praised by users"),
            ("love it", "Users love this product"),
            ("worth", "Considered worth the price"),
            ("best", "Rated as best in class"),
            ("color", "Excellent color quality"),
            ("immersive", "Immersive experience"),
        ]
        
        for pattern, title in positive_patterns:
            count = sum(1 for p in positive_posts if pattern in p.get('content', '').lower())
            if count > 0 and title not in seen:
                seen.add(title)
                positives.append({
                    "title": title,
                    "frequency": self.classify_frequency(count, len(raw_data)),
                    "mention_count": count
                })
        
        return sorted(positives, key=lambda x: x['mention_count'], reverse=True)


class RedditScraper(BaseScraper):
    """
    Real Reddit API scraper.
    
    Requires Reddit API credentials. Use this once your API access is approved.
    """
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        super().__init__("reddit")
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.access_token = None
        self.token_expires = None
        self.subreddits = ["monitors", "ultrawidemasterrace", "buildapc", "hardware"]
    
    def _get_access_token(self):
        """Get OAuth access token from Reddit."""
        if self.access_token and self.token_expires and datetime.utcnow() < self.token_expires:
            return self.access_token
        
        auth = requests.auth.HTTPBasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        headers = {"User-Agent": self.user_agent}
        
        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data=data,
            headers=headers
        )
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expires = datetime.utcnow() + timedelta(seconds=token_data["expires_in"] - 60)
        
        return self.access_token
    
    def search_product(self, product_name: str, brand: str = None) -> List[Dict]:
        """Search Reddit for product mentions."""
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.user_agent
        }
        
        query = f"{brand} {product_name}" if brand else product_name
        results = []
        
        for subreddit in self.subreddits:
            try:
                url = f"https://oauth.reddit.com/r/{subreddit}/search"
                params = {
                    "q": query,
                    "restrict_sr": True,
                    "sort": "relevance",
                    "limit": 100,
                    "t": "year"  # Last year
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                for post in data.get("data", {}).get("children", []):
                    post_data = post.get("data", {})
                    results.append({
                        "source_url": f"https://reddit.com{post_data.get('permalink', '')}",
                        "title": post_data.get("title", ""),
                        "content": post_data.get("selftext", ""),
                        "date": datetime.fromtimestamp(post_data.get("created_utc", 0)).isoformat(),
                        "sentiment": self._analyze_sentiment(post_data.get("title", "") + post_data.get("selftext", "")),
                        "upvotes": post_data.get("ups", 0),
                        "subreddit": subreddit,
                        "comment_count": post_data.get("num_comments", 0),
                    })
                
            except requests.exceptions.RequestException as e:
                print(f"Reddit API error for r/{subreddit}: {e}")
        
        self.last_fetch = datetime.utcnow()
        return results
    
    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis based on keywords."""
        text_lower = text.lower()
        
        negative_words = ['issue', 'problem', 'broken', 'defect', 'return', 'disappointed',
                         'terrible', 'awful', 'worst', 'avoid', 'warning', 'regret']
        positive_words = ['love', 'amazing', 'great', 'excellent', 'perfect', 'best',
                         'recommend', 'awesome', 'fantastic', 'worth']
        
        neg_count = sum(1 for word in negative_words if word in text_lower)
        pos_count = sum(1 for word in positive_words if word in text_lower)
        
        if neg_count > pos_count:
            return "negative"
        elif pos_count > neg_count:
            return "positive"
        return "neutral"
    
    def extract_issues(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract issues from Reddit data using NLP patterns."""
        # Similar to mock implementation but with real data
        # TODO: Add more sophisticated NLP
        return MockRedditScraper().extract_issues(raw_data)
    
    def extract_positives(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract positives from Reddit data."""
        return MockRedditScraper().extract_positives(raw_data)


# Use mock by default until Reddit API is approved
def get_reddit_scraper(client_id: str = None, client_secret: str = None, user_agent: str = None):
    """
    Factory function to get the appropriate Reddit scraper.
    
    Returns MockRedditScraper if no credentials provided,
    otherwise returns real RedditScraper.
    """
    if client_id and client_secret and user_agent:
        return RedditScraper(client_id, client_secret, user_agent)
    else:
        print("Using mock Reddit data (no credentials provided)")
        return MockRedditScraper()


# Test
if __name__ == "__main__":
    scraper = get_reddit_scraper()  # Will use mock
    
    print("Searching for Samsung Odyssey G9...")
    results = scraper.search_product("Odyssey G9", "Samsung")
    
    print(f"\nFound {len(results)} posts")
    
    issues = scraper.extract_issues(results)
    print(f"\nExtracted {len(issues)} issues:")
    for issue in issues[:5]:
        print(f"  - {issue['title']} ({issue['severity']}, {issue['mention_count']} mentions)")
    
    positives = scraper.extract_positives(results)
    print(f"\nExtracted {len(positives)} positives:")
    for pos in positives[:3]:
        print(f"  - {pos['title']} ({pos['mention_count']} mentions)")
