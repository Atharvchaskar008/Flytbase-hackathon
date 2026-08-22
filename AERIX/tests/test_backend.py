"""
Quick test script to verify backend APIs are working
Run this after starting the backend server
"""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n1. Testing Health Endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    return response.status_code == 200

def test_db_health():
    """Test database health"""
    print("\n2. Testing Database Connection...")
    response = requests.get(f"{BASE_URL}/health/db")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    return response.status_code == 200

def test_list_videos():
    """Test list videos endpoint"""
    print("\n3. Testing List Videos...")
    response = requests.get(f"{BASE_URL}/upload/videos")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Total videos: {len(data)}")
    if data:
        print(f"   First video: {data[0]}")
    return response.status_code == 200

def test_search_status():
    """Test search status"""
    print("\n4. Testing Search Status...")
    response = requests.get(f"{BASE_URL}/search/status")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_search_suggestions():
    """Test search suggestions"""
    print("\n5. Testing Search Suggestions...")
    response = requests.get(f"{BASE_URL}/search/suggestions")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if 'suggestions' in data:
        print(f"   Categories: {list(data['suggestions'].keys())}")
        print(f"   Total suggestions: {data['total_suggestions']}")
    return response.status_code == 200

def main():
    print("=" * 60)
    print("TRACE Backend API Test")
    print("=" * 60)
    print("\nMake sure backend is running on http://localhost:8000")
    print("\nStarting tests...")
    
    results = []
    
    try:
        results.append(("Health Check", test_health()))
        results.append(("Database", test_db_health()))
        results.append(("List Videos", test_list_videos()))
        results.append(("Search Status", test_search_status()))
        results.append(("Search Suggestions", test_search_suggestions()))
        
        print("\n" + "=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        for name, passed in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status:8} - {name}")
        
        all_passed = all(result[1] for result in results)
        if all_passed:
            print("\n✅ All tests passed! Backend is working correctly.")
        else:
            print("\n❌ Some tests failed. Check the output above.")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to backend!")
        print("   Make sure the backend server is running:")
        print("   cd backend")
        print("   uvicorn backend.main:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
