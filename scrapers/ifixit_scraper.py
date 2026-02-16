"""
iFixit Scraper

iFixit has repairability scores, teardowns, and known issues for many products.
They have a public API - no key needed.

API docs: https://www.ifixit.com/api/2.0/doc
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime

import sys
sys.path.append(str(__file__).rsplit('/', 1)[0])
from base import BaseScraper


class IFixitScraper(BaseScraper):
    """Scraper for iFixit repair data."""
    
    BASE_URL = "https://www.ifixit.com/api/2.0"
    
    def __init__(self):
        super().__init__("ifixit")
    
    def search_product(self, product_name: str, brand: str = None) -> List[Dict]:
        """
        Search iFixit for a product.
        """
        results = []
        
        # Combine brand and product name for better search
        query = f"{brand} {product_name}" if brand else product_name
        
        try:
            # Search for guides/teardowns
            url = f"{self.BASE_URL}/search/{query}"
            params = {"filter": "device", "limit": 10}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            for item in data.get('results', []):
                device_info = self._get_device_info(item.get('title', ''))
                if device_info:
                    results.append(device_info)
            
        except requests.exceptions.RequestException as e:
            print(f"iFixit search error: {e}")
        
        self.last_fetch = datetime.utcnow()
        return results
    
    def _get_device_info(self, device_name: str) -> Optional[Dict]:
        """Get detailed info for a specific device."""
        try:
            # Clean up device name for URL
            device_slug = device_name.replace(' ', '_')
            url = f"{self.BASE_URL}/wikis/CATEGORY/{device_slug}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            data = response.json()
            
            return {
                "source_url": f"https://www.ifixit.com/Device/{device_slug}",
                "title": data.get('title', device_name),
                "content": data.get('contents_raw', ''),
                "repairability_score": self._extract_repairability(data),
                "guides_count": len(data.get('guides', [])),
                "solutions_count": data.get('solutions', {}).get('count', 0),
                "date": data.get('modified_date'),
                "sentiment": "neutral",
            }
            
        except requests.exceptions.RequestException as e:
            print(f"iFixit device info error for {device_name}: {e}")
            return None
    
    def _extract_repairability(self, data: dict) -> Optional[int]:
        """Extract repairability score from device data."""
        # iFixit stores this in different places depending on the device
        score = data.get('repairability_score')
        if score:
            return int(score)
        
        # Sometimes it's in the contents
        contents = data.get('contents_raw', '')
        if 'repairability' in contents.lower():
            # Try to extract score from text
            import re
            match = re.search(r'(\d+)\s*/\s*10', contents)
            if match:
                return int(match.group(1))
        
        return None
    
    def get_device_problems(self, device_name: str) -> List[Dict]:
        """
        Get known problems/solutions for a device.
        """
        problems = []
        
        try:
            device_slug = device_name.replace(' ', '_')
            url = f"{self.BASE_URL}/wikis/CATEGORY/{device_slug}/solutions"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                return []
            
            response.raise_for_status()
            data = response.json()
            
            for solution in data:
                problems.append({
                    "title": solution.get('title', ''),
                    "description": solution.get('contents_rendered', ''),
                    "url": solution.get('url', ''),
                    "views": solution.get('views', 0),
                })
            
        except requests.exceptions.RequestException as e:
            print(f"iFixit solutions error: {e}")
        
        return problems
    
    def extract_issues(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract issues from iFixit data."""
        issues = []
        
        for item in raw_data:
            # Low repairability score is an issue
            score = item.get('repairability_score')
            if score is not None and score <= 4:
                issues.append({
                    "title": f"Poor repairability score ({score}/10)",
                    "description": "This device is difficult to repair, which may lead to higher long-term costs and more e-waste.",
                    "severity": "medium" if score > 2 else "high",
                    "mention_count": 1,
                    "source_urls": [item.get('source_url')],
                    "workaround": None,
                    "status": "ongoing"
                })
        
        return issues
    
    def extract_positives(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract positives from iFixit data."""
        positives = []
        
        for item in raw_data:
            score = item.get('repairability_score')
            
            # High repairability is a positive
            if score is not None and score >= 7:
                positives.append({
                    "title": f"Excellent repairability ({score}/10)",
                    "mention_count": 1
                })
            
            # Many repair guides is a positive
            guides = item.get('guides_count', 0)
            if guides >= 10:
                positives.append({
                    "title": f"Well-documented repairs ({guides} guides available)",
                    "mention_count": guides
                })
        
        return positives
    
    def get_repairability_summary(self, product_name: str, brand: str = None) -> Dict:
        """
        Convenience method to get repairability info for a product.
        """
        raw_data = self.search_product(product_name, brand)
        
        if not raw_data:
            return {
                "found": False,
                "repairability_score": None,
                "message": "Product not found in iFixit database"
            }
        
        # Get the best match
        best_match = raw_data[0]
        issues = self.extract_issues([best_match])
        positives = self.extract_positives([best_match])
        
        return {
            "found": True,
            "product_name": best_match.get('title'),
            "repairability_score": best_match.get('repairability_score'),
            "guides_count": best_match.get('guides_count', 0),
            "source_url": best_match.get('source_url'),
            "issues": issues,
            "positives": positives,
            "checked_at": datetime.utcnow().isoformat()
        }


# Test the scraper
if __name__ == "__main__":
    scraper = IFixitScraper()
    
    print("Searching iFixit for MacBook Pro...")
    result = scraper.get_repairability_summary("MacBook Pro", "Apple")
    
    print(f"\nFound: {result['found']}")
    if result['found']:
        print(f"Product: {result['product_name']}")
        print(f"Repairability: {result['repairability_score']}/10")
        print(f"Repair guides: {result['guides_count']}")
        print(f"URL: {result['source_url']}")
