"""
CPSC (Consumer Product Safety Commission) Recall Database Scraper

This scrapes the official US government recall database.
No API key needed - it's public data.

API docs: https://www.cpsc.gov/Recalls/CPSC-Recalls-Application-Program-Interface-API-Information
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime
import time

import sys
sys.path.append(str(__file__).rsplit('/', 1)[0])
from base import BaseScraper


class CPSCScraper(BaseScraper):
    """Scraper for CPSC recall database."""
    
    BASE_URL = "https://www.saferproducts.gov/RestWebServices"
    
    def __init__(self):
        super().__init__("cpsc")
    
    def search_product(self, product_name: str, brand: str = None) -> List[Dict]:
        """
        Search CPSC database for recalls related to a product.
        """
        results = []
        
        # Search recalls
        recalls = self._search_recalls(product_name)
        results.extend(recalls)
        
        # If we have a brand, search that too
        if brand:
            brand_recalls = self._search_recalls(brand)
            # Deduplicate by recall ID
            existing_ids = {r.get('recall_id') for r in results}
            for recall in brand_recalls:
                if recall.get('recall_id') not in existing_ids:
                    results.append(recall)
        
        self.last_fetch = datetime.utcnow()
        return results
    
    def _search_recalls(self, query: str) -> List[Dict]:
        """Search the recall database."""
        try:
            # CPSC Recalls API
            url = f"{self.BASE_URL}/Recall"
            params = {
                "format": "json",
                "RecallTitle": query
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            for item in data:
                results.append({
                    "source_url": item.get("URL", ""),
                    "recall_id": item.get("RecallID"),
                    "title": item.get("RecallTitle", ""),
                    "content": item.get("Description", ""),
                    "date": item.get("RecallDate"),
                    "hazard": item.get("Hazard", ""),
                    "remedy": item.get("Remedy", ""),
                    "units": item.get("Units", ""),
                    "manufacturer": item.get("Manufacturers", []),
                    "sentiment": "negative",  # Recalls are always negative
                })
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"CPSC API error: {e}")
            return []
    
    def search_incidents(self, product_name: str) -> List[Dict]:
        """
        Search for incident reports (not full recalls).
        These are individual consumer complaints.
        """
        try:
            url = f"{self.BASE_URL}/Incident"
            params = {
                "format": "json",
                "ProductType": product_name
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            for item in data:
                results.append({
                    "source_url": "",
                    "incident_id": item.get("IncidentId"),
                    "title": item.get("ProductType", ""),
                    "content": item.get("IncidentDescription", ""),
                    "date": item.get("IncidentDate"),
                    "injury": item.get("Injury", "No"),
                    "sentiment": "negative",
                })
            
            return results
            
        except requests.exceptions.RequestException as e:
            print(f"CPSC Incident API error: {e}")
            return []
    
    def extract_issues(self, raw_data: List[Dict]) -> List[Dict]:
        """Extract issues from CPSC data."""
        issues = []
        
        for item in raw_data:
            # Each recall is essentially an issue
            if item.get('recall_id'):
                severity = 'critical' if item.get('injury') == 'Yes' or 'fire' in item.get('hazard', '').lower() else 'high'
                
                issues.append({
                    "title": f"RECALL: {item.get('title', 'Unknown issue')}",
                    "description": item.get('hazard', item.get('content', '')),
                    "severity": severity,
                    "mention_count": 1,  # Official recall counts as significant
                    "source_urls": [item.get('source_url')],
                    "workaround": item.get('remedy', None),
                    "first_reported": item.get('date'),
                    "status": "ongoing"  # Recalls are ongoing until resolved
                })
        
        return issues
    
    def extract_positives(self, raw_data: List[Dict]) -> List[Dict]:
        """CPSC data doesn't have positives - it's a recall database."""
        return []
    
    def check_product_recalls(self, product_name: str, brand: str = None) -> Dict:
        """
        Convenience method to check if a product has any recalls.
        
        Returns a summary dict.
        """
        raw_data = self.search_product(product_name, brand)
        issues = self.extract_issues(raw_data)
        
        return {
            "has_recalls": len(issues) > 0,
            "recall_count": len(issues),
            "recalls": issues,
            "checked_at": datetime.utcnow().isoformat()
        }


# Test the scraper
if __name__ == "__main__":
    scraper = CPSCScraper()
    
    # Test with a known recalled product type
    print("Searching for monitor recalls...")
    results = scraper.check_product_recalls("computer monitor", "Samsung")
    
    print(f"\nFound {results['recall_count']} recalls")
    for recall in results['recalls'][:3]:
        print(f"  - {recall['title']}")
        print(f"    Severity: {recall['severity']}")
        print(f"    Date: {recall.get('first_reported', 'Unknown')}")
        print()
