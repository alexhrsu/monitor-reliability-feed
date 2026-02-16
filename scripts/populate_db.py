"""
Populate Database Script

This script populates the database with monitor data by:
1. Adding known monitor products
2. Fetching data from available sources (CPSC, iFixit, mock Reddit)
3. Calculating reliability scores
"""

import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'scrapers')

from database import init_database, add_product, get_connection
from scoring import calculate_reliability_score, save_reliability_score, save_issues, save_positives
from reddit_scraper import get_reddit_scraper
from cpsc_scraper import CPSCScraper
from ifixit_scraper import IFixitScraper

from datetime import datetime


# Monitor products to track
MONITORS = [
    {
        "id": "samsung-odyssey-g9-2024",
        "name": "Samsung Odyssey G9 (2024)",
        "brand": "Samsung",
        "category": "monitors",
        "subcategory": "ultrawide",
        "specs": {"size": "49 inch", "resolution": "5120x1440", "refresh": "240Hz", "panel": "VA"}
    },
    {
        "id": "lg-27gp950-b",
        "name": "LG 27GP950-B",
        "brand": "LG",
        "category": "monitors",
        "subcategory": "4k-gaming",
        "specs": {"size": "27 inch", "resolution": "3840x2160", "refresh": "160Hz", "panel": "IPS"}
    },
    {
        "id": "asus-rog-pg42uq",
        "name": "ASUS ROG Swift PG42UQ",
        "brand": "ASUS",
        "category": "monitors",
        "subcategory": "oled-gaming",
        "specs": {"size": "42 inch", "resolution": "3840x2160", "refresh": "138Hz", "panel": "OLED"}
    },
    {
        "id": "dell-aw3423dwf",
        "name": "Dell Alienware AW3423DWF",
        "brand": "Dell",
        "category": "monitors",
        "subcategory": "ultrawide-oled",
        "specs": {"size": "34 inch", "resolution": "3440x1440", "refresh": "165Hz", "panel": "QD-OLED"}
    },
    {
        "id": "gigabyte-m32u",
        "name": "Gigabyte M32U",
        "brand": "Gigabyte",
        "category": "monitors",
        "subcategory": "4k-gaming",
        "specs": {"size": "32 inch", "resolution": "3840x2160", "refresh": "144Hz", "panel": "IPS"}
    },
    {
        "id": "lg-27gn950-b",
        "name": "LG 27GN950-B",
        "brand": "LG",
        "category": "monitors",
        "subcategory": "4k-gaming",
        "specs": {"size": "27 inch", "resolution": "3840x2160", "refresh": "144Hz", "panel": "IPS"}
    },
    {
        "id": "samsung-odyssey-g7-32",
        "name": "Samsung Odyssey G7 32\"",
        "brand": "Samsung",
        "category": "monitors",
        "subcategory": "curved-gaming",
        "specs": {"size": "32 inch", "resolution": "2560x1440", "refresh": "240Hz", "panel": "VA"}
    },
    {
        "id": "asus-rog-pg279qm",
        "name": "ASUS ROG Swift PG279QM",
        "brand": "ASUS",
        "category": "monitors",
        "subcategory": "esports",
        "specs": {"size": "27 inch", "resolution": "2560x1440", "refresh": "240Hz", "panel": "IPS"}
    },
    {
        "id": "lg-48gq900-b",
        "name": "LG UltraGear 48GQ900-B",
        "brand": "LG",
        "category": "monitors",
        "subcategory": "oled-gaming",
        "specs": {"size": "48 inch", "resolution": "3840x2160", "refresh": "120Hz", "panel": "OLED"}
    },
    {
        "id": "benq-ex3210u",
        "name": "BenQ MOBIUZ EX3210U",
        "brand": "BenQ",
        "category": "monitors",
        "subcategory": "4k-gaming",
        "specs": {"size": "32 inch", "resolution": "3840x2160", "refresh": "144Hz", "panel": "IPS"}
    },
]


def populate_database():
    """Main function to populate the database."""
    
    print("=" * 60)
    print("MONITOR RELIABILITY FEED - Database Population")
    print("=" * 60)
    
    # Initialize database
    print("\n[1/5] Initializing database...")
    init_database()
    
    # Initialize scrapers
    print("\n[2/5] Initializing data scrapers...")
    reddit_scraper = get_reddit_scraper()  # Will use mock until we have credentials
    cpsc_scraper = CPSCScraper()
    ifixit_scraper = IFixitScraper()
    
    # Add products and gather data
    print("\n[3/5] Adding products and gathering data...")
    
    for i, monitor in enumerate(MONITORS):
        print(f"\n  Processing {i+1}/{len(MONITORS)}: {monitor['name']}")
        
        # Add product to database
        add_product(
            product_id=monitor['id'],
            name=monitor['name'],
            brand=monitor['brand'],
            category=monitor['category'],
            subcategory=monitor.get('subcategory'),
            specs=monitor.get('specs')
        )
        
        # Gather data from sources
        all_issues = []
        all_positives = []
        recall_data = None
        repair_data = None
        
        # Reddit (mock for now)
        print(f"    - Fetching Reddit data...")
        try:
            reddit_data = reddit_scraper.search_product(monitor['name'], monitor['brand'])
            reddit_issues = reddit_scraper.extract_issues(reddit_data)
            reddit_positives = reddit_scraper.extract_positives(reddit_data)
            all_issues.extend(reddit_issues)
            all_positives.extend(reddit_positives)
            print(f"      Found {len(reddit_issues)} issues, {len(reddit_positives)} positives")
        except Exception as e:
            print(f"      Error: {e}")
        
        # CPSC Recalls
        print(f"    - Checking CPSC recalls...")
        try:
            recall_data = cpsc_scraper.check_product_recalls(monitor['name'], monitor['brand'])
            if recall_data.get('has_recalls'):
                all_issues.extend(recall_data.get('recalls', []))
                print(f"      Found {recall_data['recall_count']} recalls!")
            else:
                print(f"      No recalls found")
        except Exception as e:
            print(f"      Error: {e}")
            recall_data = {"has_recalls": False, "recall_count": 0}
        
        # iFixit (may not have data for all monitors)
        print(f"    - Checking iFixit...")
        try:
            repair_data = ifixit_scraper.get_repairability_summary(monitor['name'], monitor['brand'])
            if repair_data.get('found'):
                print(f"      Repairability: {repair_data.get('repairability_score')}/10")
                all_issues.extend(repair_data.get('issues', []))
                all_positives.extend(repair_data.get('positives', []))
            else:
                print(f"      Not found in iFixit database")
        except Exception as e:
            print(f"      Error: {e}")
            repair_data = {"found": False}
        
        # Calculate reliability score
        print(f"    - Calculating reliability score...")
        score_data = calculate_reliability_score(
            issues=all_issues,
            positives=all_positives,
            recall_data=recall_data,
            repairability=repair_data
        )
        
        print(f"      Score: {score_data['score']}/100 ({score_data['grade']}) - {score_data['confidence']} confidence")
        
        # Save to database
        print(f"    - Saving to database...")
        save_reliability_score(monitor['id'], score_data)
        save_issues(monitor['id'], all_issues)
        save_positives(monitor['id'], all_positives)
    
    # Print summary
    print("\n" + "=" * 60)
    print("POPULATION COMPLETE")
    print("=" * 60)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    product_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM issues")
    issue_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reliability_scores")
    score_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\nDatabase now contains:")
    print(f"  - {product_count} products")
    print(f"  - {issue_count} issues")
    print(f"  - {score_count} reliability scores")
    
    print("\n[5/5] Done! You can now run the API with:")
    print("  cd src && python main.py")


if __name__ == "__main__":
    populate_database()
