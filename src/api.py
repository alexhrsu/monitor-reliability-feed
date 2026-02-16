"""
Monitor Reliability Feed API

Run with: python main.py
API will be at: http://localhost:8000

Install dependencies first:
    pip install flask
"""

from flask import Flask, jsonify, request
from datetime import datetime
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_connection, init_database

app = Flask(__name__)


@app.route("/")
def root():
    """Health check and API info."""
    return jsonify({
        "name": "Monitor Reliability Feed",
        "version": "0.1.0",
        "status": "operational",
        "docs": "See /docs for available endpoints",
        "endpoints": {
            "get_product": "GET /products/<product_id>",
            "search_products": "GET /products/search?q=<query>",
            "compare_products": "GET /products/compare?ids=<id1>,<id2>",
            "top_products": "GET /categories/<category>/top",
            "avoid_products": "GET /categories/<category>/avoid",
            "trending_issues": "GET /issues/trending"
        }
    })


@app.route("/products/<product_id>")
def get_product(product_id):
    """Get full reliability report for a single product."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get product
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    
    if not product:
        return jsonify({"error": f"Product '{product_id}' not found"}), 404
    
    product = dict(product)
    
    # Get latest reliability score
    cursor.execute("""
        SELECT * FROM reliability_scores 
        WHERE product_id = ? 
        ORDER BY calculated_at DESC 
        LIMIT 1
    """, (product_id,))
    score_row = cursor.fetchone()
    score_row = dict(score_row) if score_row else {}
    
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
    
    # Get comparison data
    cursor.execute("""
        SELECT AVG(score) as avg_score 
        FROM reliability_scores rs
        JOIN products p ON rs.product_id = p.id
        WHERE p.category = ?
    """, (product['category'],))
    avg_row = cursor.fetchone()
    category_average = round(avg_row['avg_score']) if avg_row and avg_row['avg_score'] else None
    
    # Get better alternatives
    better_alternatives = []
    if score_row.get('score'):
        cursor.execute("""
            SELECT p.id, p.name, rs.score
            FROM products p
            JOIN reliability_scores rs ON p.id = rs.product_id
            WHERE p.category = ? AND p.id != ? AND rs.score > ?
            ORDER BY rs.score DESC
            LIMIT 3
        """, (product['category'], product_id, score_row.get('score', 0)))
        better_alternatives = [{"id": row['id'], "name": row['name'], "score": row['score']} 
                              for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        "product": {
            "id": product['id'],
            "name": product['name'],
            "brand": product['brand'],
            "category": product['category'],
            "subcategory": product.get('subcategory')
        },
        "reliability": {
            "score": score_row.get('score'),
            "grade": score_row.get('grade'),
            "confidence": score_row.get('confidence', 'low'),
            "data_points": score_row.get('data_points', 0),
            "last_updated": score_row.get('calculated_at'),
            "trend": score_row.get('trend'),
            "trend_delta": score_row.get('trend_delta'),
            "trend_period": score_row.get('trend_period')
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
        "meta": {
            "feed_version": "0.1.0",
            "query_cost": 1,
            "cache_ttl": 3600
        }
    })


@app.route("/products/search")
def search_products():
    """Search for products by name."""
    q = request.args.get('q', '')
    category = request.args.get('category')
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
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
    
    return jsonify({
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
    })


@app.route("/products/compare")
def compare_products():
    """Compare multiple products side by side."""
    ids = request.args.get('ids', '')
    
    if not ids:
        return jsonify({"error": "Query parameter 'ids' is required (comma-separated)"}), 400
    
    product_ids = [id.strip() for id in ids.split(",")]
    
    if len(product_ids) < 2:
        return jsonify({"error": "Need at least 2 products to compare"}), 400
    if len(product_ids) > 5:
        return jsonify({"error": "Maximum 5 products for comparison"}), 400
    
    products = []
    for pid in product_ids:
        with app.test_client() as client:
            response = client.get(f'/products/{pid}')
            if response.status_code == 200:
                products.append(response.get_json())
            else:
                products.append({"product": {"id": pid}, "error": "Not found"})
    
    # Determine recommendation
    valid_products = [p for p in products if 'error' not in p and p['reliability']['score']]
    
    if not valid_products:
        recommendation = {"winner": None, "reason": "Insufficient data"}
    else:
        sorted_products = sorted(valid_products, key=lambda x: x['reliability']['score'], reverse=True)
        winner = sorted_products[0]
        recommendation = {
            "winner": winner['product']['id'],
            "score": winner['reliability']['score'],
            "reason": "Highest reliability score"
        }
    
    return jsonify({
        "comparison": products,
        "recommendation": recommendation
    })


@app.route("/categories/<category>/top")
def get_top_products(category):
    """Get the most reliable products in a category."""
    limit = min(int(request.args.get('limit', 5)), 20)
    
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
        return jsonify({"error": f"No products found in category '{category}'"}), 404
    
    return jsonify({
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
    })


@app.route("/categories/<category>/avoid")
def get_products_to_avoid(category):
    """Get products with the worst reliability in a category."""
    limit = min(int(request.args.get('limit', 5)), 20)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT p.*, rs.score, rs.grade
        FROM products p
        JOIN reliability_scores rs ON p.id = rs.product_id
        WHERE p.category = ? AND rs.score < 70
        ORDER BY rs.score ASC
        LIMIT ?
    """, (category, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
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
    })


@app.route("/issues/trending")
def get_trending_issues():
    """Get trending issues across products."""
    category = request.args.get('category')
    period = request.args.get('period', '7d')
    
    conn = get_connection()
    cursor = conn.cursor()
    
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
    
    return jsonify({
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
    })


if __name__ == "__main__":
    # Initialize database on startup
    init_database()
    
    print("\n" + "="*50)
    print("MONITOR RELIABILITY FEED API")
    print("="*50)
    print("\nStarting server at http://localhost:8000")
    print("\nTry these endpoints:")
    print("  http://localhost:8000/")
    print("  http://localhost:8000/products/samsung-odyssey-g9-2024")
    print("  http://localhost:8000/products/search?q=odyssey")
    print("  http://localhost:8000/categories/monitors/top")
    print("  http://localhost:8000/categories/monitors/avoid")
    print("\n" + "="*50 + "\n")
    
    app.run(host="0.0.0.0", port=8000, debug=True)
