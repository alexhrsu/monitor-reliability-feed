"""
Reliability Scoring Engine

This calculates the overall reliability score for a product
based on data from all sources.
"""

from datetime import datetime
from typing import List, Dict, Optional
import json

import sys
sys.path.insert(0, str(__file__).rsplit('/', 2)[0] + '/src')
sys.path.insert(0, str(__file__).rsplit('/', 2)[0] + '/scrapers')

from database import get_connection


def calculate_reliability_score(
    issues: List[Dict],
    positives: List[Dict],
    recall_data: Dict = None,
    repairability: Dict = None
) -> Dict:
    """
    Calculate overall reliability score for a product.
    
    Returns:
    {
        "score": 0-100,
        "grade": "A" to "F",
        "confidence": "low", "medium", or "high",
        "breakdown": { ... }
    }
    """
    
    # Start at 100 and deduct points
    score = 100
    breakdown = {}
    total_data_points = 0
    
    # === Issue Penalties ===
    issue_penalty = 0
    for issue in issues:
        severity = issue.get('severity', 'low')
        mentions = issue.get('mention_count', 1)
        
        # Penalty based on severity
        severity_weights = {
            'critical': 25,  # Critical issues are major red flags
            'high': 15,
            'medium': 8,
            'low': 3
        }
        
        base_penalty = severity_weights.get(severity, 5)
        
        # Scale penalty by how common the issue is (log scale to prevent runaway)
        import math
        frequency_multiplier = 1 + (math.log10(max(mentions, 1)) * 0.3)
        
        issue_penalty += base_penalty * frequency_multiplier
        total_data_points += mentions
    
    # Cap issue penalty at 60 points
    issue_penalty = min(issue_penalty, 60)
    score -= issue_penalty
    breakdown['issue_penalty'] = round(issue_penalty, 1)
    
    # === Recall Penalty ===
    recall_penalty = 0
    if recall_data and recall_data.get('has_recalls'):
        recall_count = recall_data.get('recall_count', 0)
        recall_penalty = min(recall_count * 20, 40)  # Up to 40 points for recalls
        total_data_points += recall_count
    
    score -= recall_penalty
    breakdown['recall_penalty'] = recall_penalty
    
    # === Repairability Factor ===
    repairability_adjustment = 0
    if repairability and repairability.get('found'):
        repair_score = repairability.get('repairability_score')
        if repair_score is not None:
            # Repairability 1-10 maps to -10 to +5 adjustment
            repairability_adjustment = (repair_score - 5) * 1.5
            total_data_points += 1
    
    score += repairability_adjustment
    breakdown['repairability_adjustment'] = round(repairability_adjustment, 1)
    
    # === Positive Bonus ===
    positive_bonus = 0
    for positive in positives:
        mentions = positive.get('mention_count', 1)
        # Small bonus for positives (they matter less than negatives)
        positive_bonus += min(mentions * 0.02, 3)  # Cap each positive at 3 points
        total_data_points += mentions
    
    positive_bonus = min(positive_bonus, 10)  # Cap total positive bonus at 10
    score += positive_bonus
    breakdown['positive_bonus'] = round(positive_bonus, 1)
    
    # === Clamp score ===
    score = max(0, min(100, score))
    
    # === Calculate grade ===
    if score >= 90:
        grade = 'A'
    elif score >= 80:
        grade = 'B+'
    elif score >= 70:
        grade = 'B'
    elif score >= 60:
        grade = 'C+'
    elif score >= 50:
        grade = 'C'
    elif score >= 40:
        grade = 'D'
    else:
        grade = 'F'
    
    # === Calculate confidence ===
    if total_data_points > 500:
        confidence = 'high'
    elif total_data_points > 100:
        confidence = 'medium'
    else:
        confidence = 'low'
    
    return {
        "score": round(score),
        "grade": grade,
        "confidence": confidence,
        "data_points": total_data_points,
        "breakdown": breakdown
    }


def save_reliability_score(product_id: str, score_data: Dict, trend: str = None, 
                           trend_delta: int = None, trend_period: str = "90d"):
    """Save a calculated reliability score to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO reliability_scores 
        (product_id, score, grade, confidence, data_points, trend, trend_delta, trend_period, calculated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        product_id,
        score_data['score'],
        score_data['grade'],
        score_data['confidence'],
        score_data['data_points'],
        trend,
        trend_delta,
        trend_period,
        datetime.utcnow().isoformat()
    ))
    
    conn.commit()
    conn.close()


def save_issues(product_id: str, issues: List[Dict]):
    """Save extracted issues to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for issue in issues:
        issue_id = issue.get('id') or f"{product_id}-{hash(issue['title']) % 10000:04d}"
        
        cursor.execute("""
            INSERT OR REPLACE INTO issues
            (id, product_id, title, description, severity, frequency, 
             affected_percentage, status, first_reported, mention_count, workaround, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            issue_id,
            product_id,
            issue['title'],
            issue.get('description'),
            issue.get('severity', 'medium'),
            issue.get('frequency', 'uncommon'),
            issue.get('affected_percentage'),
            issue.get('status', 'ongoing'),
            issue.get('first_reported'),
            issue.get('mention_count', 1),
            issue.get('workaround'),
            datetime.utcnow().isoformat()
        ))
        
        # Save issue sources
        for source in issue.get('source_urls', [])[:1]:  # Just count sources for now
            source_type = 'reddit' if 'reddit' in source else 'other'
            cursor.execute("""
                INSERT OR REPLACE INTO issue_sources (issue_id, source_type, source_count)
                VALUES (?, ?, ?)
            """, (issue_id, source_type, len(issue.get('source_urls', []))))
    
    conn.commit()
    conn.close()


def save_positives(product_id: str, positives: List[Dict]):
    """Save extracted positives to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for positive in positives:
        positive_id = f"{product_id}-pos-{hash(positive['title']) % 10000:04d}"
        
        cursor.execute("""
            INSERT OR REPLACE INTO positives
            (id, product_id, title, frequency, mention_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            positive_id,
            product_id,
            positive['title'],
            positive.get('frequency'),
            positive.get('mention_count', 1)
        ))
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Test the scoring engine
    test_issues = [
        {"title": "Screen flickering", "severity": "high", "mention_count": 150},
        {"title": "Minor backlight bleed", "severity": "low", "mention_count": 50},
    ]
    
    test_positives = [
        {"title": "Great colors", "mention_count": 200},
        {"title": "Good value", "mention_count": 100},
    ]
    
    test_recalls = {"has_recalls": False, "recall_count": 0}
    test_repair = {"found": True, "repairability_score": 6}
    
    result = calculate_reliability_score(test_issues, test_positives, test_recalls, test_repair)
    
    print("Test Score Calculation:")
    print(f"  Score: {result['score']}/100 ({result['grade']})")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Data points: {result['data_points']}")
    print(f"  Breakdown: {result['breakdown']}")
