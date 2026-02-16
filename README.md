# Monitor Reliability Feed

Verified reliability data for AI agents making product recommendations.

## What is this?

This API provides reliability scores, known issues, and quality data for monitors (and eventually other product categories). It's designed to be consumed by AI agents to make better recommendations.

Instead of just "4.2 stars on Amazon", agents get:
- **Reliability scores** based on real user complaints, recalls, and repair data
- **Known issues** with severity ratings and affected percentages
- **Trend data** showing if products are getting better or worse
- **Source transparency** showing where each data point comes from

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database and populate with data
cd scripts
python populate_db.py

# Run the API
cd ../src
python main.py
```

API will be running at `http://localhost:8000`

## API Endpoints

### Get Product Reliability
```
GET /products/{product_id}
```

Returns full reliability report:
```json
{
  "product": {
    "id": "samsung-odyssey-g9-2024",
    "name": "Samsung Odyssey G9 (2024)",
    "brand": "Samsung",
    "category": "monitors"
  },
  "reliability": {
    "score": 68,
    "grade": "C+",
    "confidence": "high",
    "data_points": 2847,
    "trend": "declining"
  },
  "issues": [
    {
      "title": "Flickering at 240Hz",
      "severity": "high",
      "affected_percentage": 23,
      "mentions": 342
    }
  ],
  "positives": [...],
  "comparison": {
    "category_average": 74,
    "better_alternatives": [...]
  }
}
```

### Search Products
```
GET /products/search?q=odyssey
```

### Compare Products
```
GET /products/compare?ids=samsung-odyssey-g9-2024,lg-27gp950-b
```

### Top Products in Category
```
GET /categories/monitors/top?limit=5
```

### Products to Avoid
```
GET /categories/monitors/avoid?limit=5
```

### Trending Issues
```
GET /issues/trending?period=7d
```

## Data Sources

Currently integrated:
- **Reddit** (r/monitors, r/ultrawidemasterrace, r/buildapc) - user complaints and praise
- **CPSC** - official recall database
- **iFixit** - repairability scores

Coming soon:
- RTings professional reviews
- Amazon review analysis

## Project Structure

```
monitor-reliability-feed/
├── src/
│   ├── main.py          # FastAPI application
│   ├── database.py      # Database models and queries
│   └── scoring.py       # Reliability score calculation
├── scrapers/
│   ├── base.py          # Base scraper class
│   ├── reddit_scraper.py
│   ├── cpsc_scraper.py
│   └── ifixit_scraper.py
├── scripts/
│   └── populate_db.py   # Database population script
├── data/
│   └── reliability.db   # SQLite database (created on first run)
└── requirements.txt
```

## Configuration

### Reddit API (Optional)

Once you have Reddit API access approved, create a `.env` file:

```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=monitor-reliability-feed/0.1
```

The system will automatically switch from mock data to real Reddit data.

## License

MIT
