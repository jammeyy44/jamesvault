"""
Service layer for interacting with game providers.
"""

import requests

class Category1Service:
    """Service for interacting with Category 1 game providers."""

    def __init__(self, username, password):
        """Initialize the service with credentials."""
        self.username = username
        self.password = password
        self.BASE_URL = "https://agentserver.gameroom777.com"
        self.SESSION = requests.Session()

    def login(self):
        """Login to the game provider."""
        payload = {"username": self.username, "password": self.password}
        response = self.SESSION.post(f"{self.BASE_URL}/api/login", data=payload)
        return response.json()

    def add_user(self, new_username, new_password):
        """Add a new user to the game provider."""
        payload = {
            "username": new_username,
            "password": new_password,
            "password_confirmation": new_password,
        }
        response = self.SESSION.post(f"{self.BASE_URL}/api/player/playerInsert", data=payload)
        return response.json()