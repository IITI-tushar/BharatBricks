"""
Mock ML Endpoints for Bharat Bricks Local Development
Replaces Databricks Model Serving Endpoints

This module provides simple rule-based and keyword-based classification
to replace the AI models while running locally without Databricks.
"""

import random
from typing import List, Dict

# Department categories (matching your training data)
DEPARTMENTS = [
    "Roads & Infrastructure",
    "Water Supply",
    "Electricity",
    "Garbage Collection",
    "Public Health",
    "Education",
    "Law & Order",
    "Environment",
    "Housing",
    "Transportation",
    "Street Lighting",
    "Drainage",
    "Parks & Recreation"
]

# Government bodies (matching governing_bodies table)
GOVERNING_BODIES = [
    "Municipal Corporation Bhopal",
    "Public Works Department (PWD)",
    "Water Supply Department",
    "Madhya Pradesh State Electricity Board",
    "Health Department MP",
    "Education Department MP",
    "Police Department MP",
    "Environment Department MP",
    "Housing Board MP",
    "Transport Department MP"
]

# Keyword mapping for classification
KEYWORD_MAPPINGS = {
    "Roads & Infrastructure": [
        "road", "pothole", "bridge", "highway", "street", "pavement", 
        "construction", "repair", "crack", "damage", "infrastructure"
    ],
    "Water Supply": [
        "water", "tap", "pipeline", "supply", "leak", "drinking water",
        "shortage", "contamination", "pipe burst", "pressure"
    ],
    "Electricity": [
        "electricity", "power", "outage", "transformer", "wire", "pole",
        "blackout", "voltage", "current", "meter", "bill"
    ],
    "Garbage Collection": [
        "garbage", "waste", "trash", "dirty", "cleanliness", "dustbin",
        "sanitation", "disposal", "litter", "dump"
    ],
    "Public Health": [
        "health", "hospital", "clinic", "doctor", "medicine", "disease",
        "vaccination", "ambulance", "medical", "hygiene"
    ],
    "Education": [
        "school", "education", "teacher", "student", "college", "university",
        "classroom", "learning", "exam", "admission"
    ],
    "Law & Order": [
        "police", "crime", "theft", "safety", "law", "security", "robbery",
        "violence", "harassment", "emergency"
    ],
    "Environment": [
        "pollution", "environment", "tree", "park", "air quality", "noise",
        "green", "forest", "wildlife", "conservation"
    ],
    "Street Lighting": [
        "light", "street light", "lamp", "dark", "illumination", "bulb"
    ],
    "Drainage": [
        "drainage", "drain", "sewage", "overflow", "clog", "stagnant",
        "rainwater", "flood"
    ],
    "Housing": [
        "housing", "building", "apartment", "slum", "construction permit",
        "illegal construction"
    ],
    "Transportation": [
        "bus", "transport", "traffic", "vehicle", "auto", "rickshaw",
        "public transport", "congestion"
    ]
}

def classify_complaint(text: str) -> str:
    """
    Mock classifier using keyword matching
    
    Args:
        text: Combined title + description of complaint
        
    Returns:
        Predicted department category
    """
    text_lower = text.lower()
    
    # Score each category
    scores = {}
    for category, keywords in KEYWORD_MAPPINGS.items():
        score = sum(1 for keyword in keywords if keyword in text_lower)
        if score > 0:
            scores[category] = score
    
    # Return highest scoring category
    if scores:
        return max(scores, key=scores.get)
    
    # Default fallback
    return random.choice(DEPARTMENTS)

def route_complaint(category: str, text: str = "") -> List[str]:
    """
    Mock router - returns relevant government bodies for a category
    
    Args:
        category: The classified category
        text: Original complaint text (optional, for advanced routing)
        
    Returns:
        List of government body names
    """
    
    # Department to government body mapping
    routing_map = {
        "Roads & Infrastructure": [
            "Municipal Corporation Bhopal",
            "Public Works Department (PWD)"
        ],
        "Water Supply": [
            "Water Supply Department",
            "Municipal Corporation Bhopal"
        ],
        "Electricity": [
            "Madhya Pradesh State Electricity Board"
        ],
        "Garbage Collection": [
            "Municipal Corporation Bhopal"
        ],
        "Public Health": [
            "Health Department MP",
            "Municipal Corporation Bhopal"
        ],
        "Education": [
            "Education Department MP"
        ],
        "Law & Order": [
            "Police Department MP"
        ],
        "Environment": [
            "Environment Department MP",
            "Municipal Corporation Bhopal"
        ],
        "Street Lighting": [
            "Municipal Corporation Bhopal",
            "Madhya Pradesh State Electricity Board"
        ],
        "Drainage": [
            "Municipal Corporation Bhopal",
            "Public Works Department (PWD)"
        ],
        "Housing": [
            "Housing Board MP",
            "Municipal Corporation Bhopal"
        ],
        "Transportation": [
            "Transport Department MP",
            "Municipal Corporation Bhopal"
        ]
    }
    
    # Get bodies for this category, default to Municipal Corporation
    bodies = routing_map.get(category, ["Municipal Corporation Bhopal"])
    
    return bodies

def estimate_priority(text: str, category: str) -> str:
    """
    Estimate complaint priority based on text
    
    Returns: 'low', 'medium', or 'high'
    """
    text_lower = text.lower()
    
    # High priority keywords
    urgent_keywords = ["urgent", "emergency", "danger", "accident", "injury", "death", "critical"]
    if any(word in text_lower for word in urgent_keywords):
        return "high"
    
    # Medium priority (default)
    return "medium"

def estimate_resolution_time(category: str, priority: str) -> int:
    """
    Estimate resolution time in hours
    
    Returns: Estimated hours to resolution
    """
    base_times = {
        "Law & Order": 24,
        "Public Health": 48,
        "Electricity": 48,
        "Water Supply": 48,
        "Roads & Infrastructure": 72,
        "Garbage Collection": 24,
        "Street Lighting": 24,
        "Drainage": 48,
    }
    
    base = base_times.get(category, 72)
    
    # Adjust for priority
    if priority == "high":
        return base // 2
    elif priority == "low":
        return base * 2
    
    return base

# For testing
if __name__ == "__main__":
    test_cases = [
        "There is a huge pothole on MG Road causing accidents",
        "No water supply in our area for 3 days",
        "Garbage not collected for a week, very dirty",
        "Street lights not working, area is very dark at night"
    ]
    
    print("🧪 Testing Mock ML Endpoints\n")
    for text in test_cases:
        category = classify_complaint(text)
        bodies = route_complaint(category)
        priority = estimate_priority(text, category)
        hours = estimate_resolution_time(category, priority)
        
        print(f"Text: {text}")
        print(f"  → Category: {category}")
        print(f"  → Routed to: {', '.join(bodies)}")
        print(f"  → Priority: {priority}")
        print(f"  → Est. resolution: {hours}h")
        print()
