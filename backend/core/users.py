"""Fake User Store"""

from core.security import hash_password
from core.rbac import Role

fake_users_db = {
    "avishek": {
        "username": "avishek",
        "hashed_password": hash_password("secret123"),
        "role": Role.USER.value,
    },

    "admin": {
        "username": "admin",
        "hashed_password": hash_password("adminpass"),
        "role": Role.ADMIN.value,
    },
}