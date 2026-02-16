"""
Monitor Reliability Feed API

This is the main API that agents will call to get reliability data.

Supports both FastAPI and Flask - will use whichever is available.
"""

from datetime import datetime
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_connection, init_database

# Try FastAPI first, fall back to Flask
try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    USE_FASTAPI = True
except ImportError:
    from flask import Flask, jsonify, request, abort
    USE_FASTAPI = False

if USE_FASTAPI:
    app = FastAPI(
        title="Monitor Reliability Feed",
        description="Verified reliability data for AI agents making product recommendations",
        version="0.1.0"
    )
else:
    app = Flask(__name__)

# Allow cross-origin requests (for web demos)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_database()


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "name": "Monitor Reliability Feed",
        "version": "0.1.0",
        "status": "operational",
        "endpoints": {
            "get_product": "/products/{product_id}",
            "search_products": "/products/search?q=",
            "compare_products": "/products/compare?ids=",
            "top_products": "/categories/{category}/top",
            "avoid_products": "/categories/{category}/avoid",
            "trending_issues": "/issues/trending"
        }
    }


@app.get("/products/{product_id}")
async def get_product(product_id: str):
    """
    Get full reliability report for a single product.
    
    This is the main endpoint agents will use.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get product
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    
    product = dict(product)
    
    # Get latest reliability score
    cursor.execute("""
        SELECT * FROM reliability_scores 
        WHERE product_id = ? 
        ORDER BY calculated_at DESC 
        LIMIT 1
    """, (product_id,))
    score_row = cursor.fetchone()
    
    # Get issues
    cursor.execute("""
        SELECT * FROM issues 
        WHERE product_id = ? 
        ORDER BY 
            CASE severity 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                WHEN 'low' THEN 4 
            END,
            mention_count DESC
    """, (product_id,))
    issues = [dict(row) for row in cursor.fetchall()]
    
    # Get issue sources
    for issue in issues:
        cursor.execute("""
            SELECT source_type, source_count 
            FROM issue_sources 
            WHERE issue_id = ?
        """, (issue['id'],))
        issue['sources'] = [row['source_type'] for row in cursor.fetchall()]
    
    # Get positives
    cursor.execute("""
        SELECT * FROM positives 
        WHERE product_id = ? 
        ORDER BY mention_count DESC
    """, (product_id,))
    positives = [dict(row) for row in cursor.fetchall()]
    
    # Get source summary
    cursor.execute("""
        SELECT source_type, COUNT(*) as count 
        FROM source_data 
        WHERE product_id = ? 
        GROUP BY source_type
    """, (product_id,))
    sources = {row['source_type']: {"data_points": row['count']} for row in cursor.fetchall()}
    
    # Get comparison data (category average and better alternatives)
    cursor.execute("""
        SELECT AVG(score) as avg_score 
        FROM reliability_scores rs
        JOIN products p ON rs.product_id = p.id
        WHERE p.category = ?
    """, (product['category'],))
    avg_row = cursor.fetchone()
    category_average = round(avg_row['avg_score']) if avg_row and avg_row['avg_score'] else None
    
    # Get better alternatives
    cursor.execute("""
        SELECT p.id, p.name, rs.score
        FROM products p
        JOIN reliability_scores rs ON p.id = rs.product_id
        WHERE p.category = ? AND p.id != ? AND rs.score > ?
        ORDER BY rs.score DESC
        LIMIT 3
    """, (product['category'], product_id, score_row['score'] if score_row else 0))
    better_alternatives = [{"id": row['id'], "name": row['name'], "score": row['score']} 
                          for row in cursor.fetchall()]
    
    conn.close()
    
    # Build response
    response = {
        "product": {
            "id": product['id'],
            "name": product['name'],
            "brand": product['brand'],
            "category": product['category'],
            "subcategory": product.get('subcategory')
        },
        "reliability": {
            "score": score_row['score'] if score_row else None,
            "grade": score_row['grade'] if score_row else None,
            "confidence": score_row['confidence'] if score_row else "low",
            "data_points": score_row['data_points'] if score_row else 0,
            "last_updated": score_row['calculated_at'] if score_row else None,
            "trend": score_row['trend'] if score_row else None,
            "trend_delta": score_row['trend_delta'] if score_row else None,
            "trend_period": score_row['trend_period'] if score_row else None
        },
        "issues": [
            {
                "id": issue['id'],
                "title": issue['title'],
                "description": issue.get('description'),
                "severity": issue['severity'],
                "frequency": issue['frequency'],
                "affected_percentage": issue.get('affected_percentage'),
                "status": issue['status'],
                "first_reported": issue['first_reported'],
                "mentions": issue['mention_count'],
                "sources": issue.get('sources', []),
                "workaround": issue.get('workaround')
            }
            for issue in issues
        ],
        "positives": [
            {
                "title": pos['title'],
                "mention_frequency": pos['frequency'],
                "mentions": pos['mention_count']
            }
            for pos in positives
        ],
        "comparison": {
            "category_average": category_average,
            "better_alternatives": better_alternatives
        },
        "sources": sources,
        "meta": {
            "feed_version": "0.1.0",
            "query_cost": 1,
            "cache_ttl": 3600
        }
    }
    
    return response


@app.get("/products/search")
async def search_products(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, le=50)
):
    """Search for products by name."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT p.*, rs.score, rs.grade
        FROM products p
        LEFT JOIN reliability_scores rs ON p.id = rs.product_id
        WHERE p.name LIKE ?
    """
    params = [f"%{q}%"]
    
    if category:
        query += " AND p.category = ?"
        params.append(category)
    
    query += " ORDER BY rs.score DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "query": q,
        "count": len(results),
        "results": [
            {
                "id": r['id'],
                "name": r['name'],
                "brand": r['brand'],
                "category": r['category'],
                "score": r.get('score'),
                "grade": r.get('grade')
            }
            for r in results
        ]
    }


@app.get("/products/compare")
async def compare_products(
    ids: str = Query(..., description="Comma-separated product IDs")
):
    """Compare multiple products side by side."""
    product_ids = [id.strip() for id in ids.split(",")]
    
    if len(product_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 products to compare")
    if len(product_ids) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 products for comparison")
    
    products = []
    for pid in product_ids:
        try:
            product = await get_product(pid)
            products.append(product)
        except HTTPException:
            products.append({"product": {"id": pid}, "error": "Not found"})
    
    return {
        "comparison": products,
        "recommendation": _get_recommendation(products)
    }


def _get_recommendation(products: list) -> dict:
    """Generate a recommendation based on compared products."""
    valid_products = [p for p in products if 'error' not in p and p['reliability']['score']]
    
    if not valid_products:
        return {"winner": None, "reason": "Insufficient data"}
    
    # Sort by score
    sorted_products = sorted(valid_products, key=lambda x: x['reliability']['score'], reverse=True)
    winner = sorted_products[0]
    
    # Check for critical issues
    critical_issues = [i for i in winner.get('issues', []) if i['severity'] == 'critical']
    
    if critical_issues:
        return {
            "winner": winner['product']['id'],
            "score": winner['reliability']['score'],
            "warning": f"Has {len(critical_issues)} critical issue(s)",
            "reason": "Highest score but has critical issues to consider"
        }
    
    return {
        "winner": winner['product']['id'],
        "score": winner['reliability']['score'],
        "reason": "Highest reliability score with no critical issues"
    }


@app.get("/categories/{category}/top")
async def get_top_products(
    category: str,
    limit: int = Query(5, le=20)
):
    """Get the most reliable products in a category."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, rs.score, rs.grade, rs.confidence
        FROM products p
        JOIN reliability_scores rs ON p.id = rs.product_id
        WHERE p.category = ?
        ORDER BY rs.score DESC
        LIMIT ?
    """, (category, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not results:
        raise HTTPException(status_code=404, detail=f"No products found in category '{category}'")
    
    return {
        "category": category,
        "count": len(results),
        "top_products": [
            {
                "rank": i + 1,
                "id": r['id'],
                "name": r['name'],
                "brand": r['brand'],
                "score": r['score'],
                "grade": r['grade'],
                "confidence": r['confidence']
            }
            for i, r in enumerate(results)
        ]
    }


@app.get("/categories/{category}/avoid")
async def get_products_to_avoid(
    category: str,
    limit: int = Query(5, le=20)
):
    """Get products with the worst reliability in a category."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, rs.score, rs.grade
        FROM products p
        JOIN reliability_scores rs ON p.id = rs.product_id
        WHERE p.category = ? AND rs.score < 60
        ORDER BY rs.score ASC
        LIMIT ?
    """, (category, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "category": category,
        "count": len(results),
        "products_to_avoid": [
            {
                "id": r['id'],
                "name": r['name'],
                "brand": r['brand'],
                "score": r['score'],
                "grade": r['grade']
            }
            for r in results
        ]
    }


@app.get("/issues/trending")
async def get_trending_issues(
    category: Optional[str] = Query(None),
    period: str = Query("7d", regex="^(24h|7d|30d)$")
):
    """Get trending issues across products."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # For now, just get recent issues sorted by mention count
    # TODO: Implement proper trending algorithm with time decay
    
    query = """
        SELECT i.*, p.name as product_name, p.brand
        FROM issues i
        JOIN products p ON i.product_id = p.id
    """
    params = []
    
    if category:
        query += " WHERE p.category = ?"
        params.append(category)
    
    query += " ORDER BY i.mention_count DESC, i.last_reported DESC LIMIT 10"
    
    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {
        "period": period,
        "category": category,
        "trending_issues": [
            {
                "product_id": r['product_id'],
                "product_name": r['product_name'],
                "brand": r['brand'],
                "issue": r['title'],
                "severity": r['severity'],
                "mentions": r['mention_count'],
                "first_reported": r['first_reported']
            }
            for r in results
        ]
    }


# ============================================================================
# Run the server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
