"""Tests for the Flask web routes."""

import pytest
from unittest.mock import patch
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_get(client):
    """Test that the homepage loads successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Winter Smog Household Assistant" in response.data

@patch('app.build_response')
def test_index_post_valid(mock_build_response, client):
    """Test a successful form submission."""
    # Import the real function to use as the side effect
    from src.recommender import build_response as real_build_response
    
    # Force use_gemini=False on every call
    def side_effect(location_id, location_name, profile, use_gemini=True):
        return real_build_response(location_id, location_name, profile, use_gemini=False)
    
    mock_build_response.side_effect = side_effect

    response = client.post("/", data={
        "city": "Delhi",
        "area_m2": "30",
        "ceiling_height_m": "2.7",
        "windows_open": "1",
        "hours_outdoors": "2",
        "language": "en"
    })
    
    assert response.status_code == 200
    assert b"Today's Air Quality" in response.data
    # Ensure the deterministic template text is used (because use_gemini=False)
    assert b"Indoor estimate uses ratio" in response.data

def test_index_post_invalid(client):
    """Test form submission with missing/invalid data to ensure graceful error handling."""
    response = client.post("/", data={
        "area_m2": "invalid_string",
    })
    assert response.status_code == 200
    assert b"Could not read your input" in response.data