"""
News API service for fetching real news events.
Uses NewsAPI.org for news articles and geocoding for location data.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class NewsService:
    """Service for fetching real news articles."""
    
    def __init__(self):
        """Initialize News API client."""
        self.api_key = os.getenv("NEWS_API_KEY")
        self.base_url = "https://newsapi.org/v2"
        
    def fetch_news(
        self,
        date: str,
        bbox: Dict[str, float],
        language: str = "en",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Fetch news articles for a specific date and region.
        
        Args:
            date: Date in YYYY-MM-DD format
            bbox: Bounding box with west, south, east, north
            language: Language code (en, zh, etc.)
            max_results: Maximum number of articles to fetch
            
        Returns:
            List of news articles with title, description, url, etc.
        """
        if not self.api_key:
            # Fallback: return empty list if no API key
            print("Warning: NEWS_API_KEY not set. Using Gemini-only mode.")
            return []
        
        try:
            # Calculate center point of bbox
            center_lat = (bbox["north"] + bbox["south"]) / 2
            center_lng = (bbox["east"] + bbox["west"]) / 2
            
            # Calculate approximate country/region from bbox
            # For now, we'll use the center point for location-based search
            
            # NewsAPI parameters
            params = {
                "apiKey": self.api_key,
                "language": language,
                "pageSize": min(max_results, 100),  # NewsAPI max is 100
                "sortBy": "relevancy",
            }
            
            # For historical dates, use "everything" endpoint
            # For recent dates, use "top-headlines" or "everything"
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                today = datetime.now().date()
                days_diff = (today - date_obj.date()).days
                
                if days_diff <= 7:
                    # Recent news - use top-headlines
                    # Note: top-headlines doesn't support date filtering well
                    # So we'll use everything endpoint with date range
                    url = f"{self.base_url}/everything"
                    params["from"] = date
                    params["to"] = date
                    # Search for news in the region (approximate)
                    params["q"] = "*"  # Get all news, filter by date
                else:
                    # Historical news - use everything endpoint
                    url = f"{self.base_url}/everything"
                    params["from"] = date
                    params["to"] = date
                    params["q"] = "*"  # Get all news for that date
                    
            except ValueError:
                # Invalid date format, use everything endpoint
                url = f"{self.base_url}/everything"
                params["q"] = "*"
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get("articles", [])
            
            # Filter and enrich articles
            enriched_articles = []
            for article in articles[:max_results]:
                if article.get("title") and article.get("title") != "[Removed]":
                    enriched_articles.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", "Unknown"),
                        "publishedAt": article.get("publishedAt", ""),
                        "content": article.get("content", ""),
                    })
            
            return enriched_articles
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching news from NewsAPI: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in NewsService: {e}")
            return []


class GeocodingService:
    """Service for geocoding locations."""
    
    def __init__(self):
        """Initialize geocoding service."""
        # Using Nominatim (OpenStreetMap) - free, no API key needed
        self.base_url = "https://nominatim.openstreetmap.org"
        
    def geocode_location(
        self,
        location_name: str,
        bbox: Optional[Dict[str, float]] = None
    ) -> Optional[Dict[str, float]]:
        """
        Geocode a location name to lat/lng coordinates.
        
        Args:
            location_name: Name of the location (city, country, etc.)
            bbox: Optional bounding box to prioritize results within viewport
            
        Returns:
            Dict with 'lat' and 'lng' keys, or None if not found
        """
        try:
            params = {
                "q": location_name,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            }
            
            # Add bbox to prioritize results within viewport
            if bbox:
                params["viewbox"] = f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"
                params["bounded"] = 1
            
            headers = {
                "User-Agent": "Atlantis-WorldNews/1.0"  # Required by Nominatim
            }
            
            response = requests.get(
                f"{self.base_url}/search",
                params=params,
                headers=headers,
                timeout=5
            )
            response.raise_for_status()
            
            results = response.json()
            if results and len(results) > 0:
                result = results[0]
                return {
                    "lat": float(result.get("lat", 0)),
                    "lng": float(result.get("lon", 0)),
                    "display_name": result.get("display_name", location_name)
                }
            
            return None
            
        except Exception as e:
            print(f"Error geocoding location '{location_name}': {e}")
            return None
    
    def find_location_in_article(
        self,
        article: Dict[str, Any],
        bbox: Dict[str, float]
    ) -> Optional[Dict[str, float]]:
        """
        Extract and geocode location from article content.
        
        Args:
            article: News article dict
            bbox: Bounding box to prioritize locations within viewport
            
        Returns:
            Dict with 'lat', 'lng', and 'display_name', or None if not found
        """
        # Combine title, description, and content for location extraction
        text = f"{article.get('title', '')} {article.get('description', '')} {article.get('content', '')}"
        
        # Try to extract location mentions (this is simplified - could use NLP)
        # For now, we'll let Gemini extract the location from the article
        
        return None  # Will be handled by Gemini with better context

