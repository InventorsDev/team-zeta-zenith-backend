# test_sprint3.py
import requests
import random
import json
import os

BASE_URL = "http://localhost:8000/api/v1/ml/sprint3"

# Load dataset from notebooks/expanded_tickets.json
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(PROJECT_ROOT, "notebooks", "expanded_tickets.json")

with open(DATA_PATH, "r") as f:
    tickets = json.load(f)

# Pick random samples for tests
sample_tickets = random.sample(tickets, 5)
sample_texts = [t["text"] for t in sample_tickets]


def test_similarity():
    print("\n--- Similarity Detection ---")
    resp = requests.post(
        f"{BASE_URL}/similarity",
        json={
            "text": "I was charged $50 extra on my monthly bill. This is incorrect.",
            "tickets": [
                "I was charged $50 extra on my monthly bill. This is incorrect.",
                "I cannot access my account. It says my password is incorrect.",
                "My subscription was renewed but I didn't authorize it."
            ]
        }
    )
    print(resp.status_code, resp.json())

def test_clustering():
    print("\n--- Clustering ---")
    resp = requests.post(
        f"{BASE_URL}/clustering",
        json={
            "texts": [
                "I was charged $50 extra on my monthly bill. This is incorrect.",
                "I cannot access my account. It says my password is incorrect.",
                "My subscription was renewed but I didn't authorize it.",
                "My account was deleted by mistake.",
                "The database connection keeps timing out."
            ]
        }
    )
    print(resp.status_code, resp.json())

def test_duplicates():
    print("\n--- Duplicate Detection ---")
    resp = requests.post(
        f"{BASE_URL}/duplicates",
        json={
            "texts": [
                "I was charged $50 extra on my monthly bill. This is incorrect.",
                "I was charged $50 extra on my monthly bill. This is incorrect.",
                "I cannot access my account. It says my password is incorrect."
            ]
        }
    )
    print(resp.status_code, resp.json())

def test_forecasting():
    print("\n--- Forecasting ---")
    resp = requests.post(
        f"{BASE_URL}/forecast",
        json={
            "tickets": [
                {"id": 1, "text": "Billing issue", "category": "billing"},
                {"id": 2, "text": "Login failed", "category": "account"},
                {"id": 3, "text": "App crash", "category": "bug"},
                {"id": 4, "text": "Dark mode feature", "category": "feature"},
                {"id": 5, "text": "2FA setup help", "category": "technical"},
            ]
        }
    )
    print(resp.status_code, resp.json())


if __name__ == "__main__":
    test_similarity()
    test_clustering()
    test_duplicates()
    test_forecasting()
