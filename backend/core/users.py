"""Fake User Store"""

from core.security import hash_password

fake_users_db = {
    "avishek": {
        "username": "avishek",
        "hashed_password": hash_password("secret123"),
        "role": "user",
    },

    "admin": {
        "username": "admin",
        "hashed_password": hash_password("adminpass"),
        "role": "admin",
    },
}