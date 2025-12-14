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
            # Parse date and check if it's too far in the past
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                today = datetime.now().date()
                days_diff = (today - date_obj.date()).days
                
                # NewsAPI only supports dates within the last ~30 days
                # For historical dates, skip NewsAPI and let Gemini generate historical events
                if days_diff > 30:
                    print(f"Date {date} is too far in the past ({days_diff} days). Skipping NewsAPI for historical dates.")
                    return []
                
                # Also check if date is in the future
                if days_diff < 0:
                    print(f"Date {date} is in the future. Skipping NewsAPI.")
                    return []
                    
            except ValueError:
                # Invalid date format, skip NewsAPI
                print(f"Invalid date format: {date}. Skipping NewsAPI.")
                return []
            
            # Calculate center point of bbox
            center_lat = (bbox["north"] + bbox["south"]) / 2
            center_lng = (bbox["east"] + bbox["west"]) / 2
            
            # NewsAPI parameters
            params = {
                "apiKey": self.api_key,
                "language": language,
                "pageSize": min(max_results, 100),  # NewsAPI max is 100
                "sortBy": "relevancy",
            }
            
            # Use everything endpoint for recent dates
            url = f"{self.base_url}/everything"
            params["from"] = date
            params["to"] = date
            
            # Use a more specific query instead of "*" which might cause issues
            # Search for general news (empty query gets recent articles)
            if days_diff <= 7:
                # Very recent - can use empty query or specific terms
                params["q"] = "news"  # More specific than "*"
            else:
                # Recent but not today - use date range
                params["q"] = "news"
            
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
            
        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors
            if e.response.status_code == 426:
                print(f"NewsAPI 426 error for date {date}: API plan restrictions or unsupported date range. Skipping NewsAPI.")
                return []
            print(f"Error fetching news from NewsAPI: {e}")
            return []
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
        bbox: Optional[Dict[str, float]] = None  # Keep parameter for backward compatibility, but don't use it
    ) -> Optional[Dict[str, float]]:
        """
        Geocode a location name to lat/lng coordinates.
        
        Args:
            location_name: Name of the location (city, country, etc.)
            bbox: DEPRECATED - Not used. Geocoding should return actual geographic coordinates.
            
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
            
            # DO NOT use viewbox parameter - geocoding should return actual geographic coordinates
            # regardless of current map viewport. This ensures pins don't shift when map moves.
            # Removed: if bbox: params["viewbox"] = ...
            
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
                # Prefer more specific results (those with more address components)
                # Sort by importance (lower is better) and type specificity
                def result_specificity(result):
                    """Calculate specificity score - lower is more specific."""
                    importance = result.get("importance", 1.0)
                    place_type = result.get("type", "")
                    # Prefer places, buildings, amenities over cities, countries
                    type_priority = {
                        "place": 1,
                        "building": 1,
                        "amenity": 2,
                        "tourism": 2,
                        "historic": 2,
                        "neighbourhood": 3,
                        "suburb": 3,
                        "city": 4,
                        "country": 5,
                    }
                    type_score = type_priority.get(place_type, 3)
                    return (type_score, importance)
                
                # Sort by specificity (more specific first)
                sorted_results = sorted(results, key=result_specificity)
                result = sorted_results[0]
                
                # Extract a more specific display name
                display_name = result.get("display_name", location_name)
                # Nominatim format: "Place, District, City, Region, Country"
                # For more specificity, we can use the address components
                address = result.get("address", {})
                if address:
                    # Build a more specific name from address components
                    specific_parts = []
                    # Order of specificity: place > neighbourhood > suburb > city > state > country
                    for key in ["place", "neighbourhood", "suburb", "city", "state", "country"]:
                        if key in address and address[key]:
                            specific_parts.append(address[key])
                    if specific_parts:
                        # Use first 2-3 parts for a specific but readable location
                        display_name = ", ".join(specific_parts[:min(3, len(specific_parts))])
                
                return {
                    "lat": float(result.get("lat", 0)),
                    "lng": float(result.get("lon", 0)),
                    "display_name": display_name
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

