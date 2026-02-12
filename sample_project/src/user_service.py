import hashlib
import re
import json
import os
from datetime import datetime, timedelta


class Database:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def save_to_disk(self, path):
        try:
            with open(path, "w") as f:
                json.dump(self.data, f, indent=2, default=str)
        except Exception:
            pass  # Silently fail - bad practice


class EmailLog:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)

    def get_history(self, username):
        return [e for e in self.records if e["to"] == username.get("email")]


class NotificationService:
    def __init__(self, smtp_host=None, smtp_port=587):
        self.smtp_host = smtp_host or "localhost"
        self.smtp_port = smtp_port

    def send_notification(self, to, subject, body):
        # Send email notification
        pass  # Implementation not provided


class AuthService:
    def __init__(self, db_path=None, smtp_host=None, smtp_port=587):
        self.db = Database()
        self.notification_service = NotificationService(smtp_host, smtp_port)

    def authenticate(self, username, password):
        user = self.db.get(username)
        if not user:
            return None

        if user.get("locked", False):
            if user.get("lock_until"):
                lock_until = datetime.fromisoformat(user["lock_until"])
                if datetime.now() < lock_until:
                    return None
                else:
                    user["locked"] = False
                    user["failed_attempts"] = 0

        hashed = self._hash_password(password, user.get("salt", ""))
        if hashed != user.get("password_hash"):
            user["failed_attempts"] = user.get("failed_attempts", 0) + 1
            if user["failed_attempts"] >= 5:
                user["locked"] = True
                user["lock_until"] = (datetime.now() + timedelta(minutes=30)).isoformat()
                self._send_notification(
                    username,
                    "Account Locked",
                    f"Your account has been locked due to {5} failed login attempts.",
                )
            return None

        user["failed_attempts"] = 0
        token = self._generate_token(username)
        self.session_tokens[token] = {
            "username": username,
            "created": datetime.now().isoformat(),
            "expires": (datetime.now() + timedelta(hours=24)).isoformat(),
        }
        user["last_login"] = datetime.now().isoformat()
        return token

    def validate_token(self, token):
        session = self.session_tokens.get(token)
        if not session:
            return False
        expires = datetime.fromisoformat(session["expires"])
        if datetime.now() > expires:
            del self.session_tokens[token]
            return False
        return True

    def logout(self, token):
        if token in self.session_tokens:
            del self.session_tokens[token]
            return True
        return False

    def _hash_password(self, password, salt):
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    def _generate_token(self, username):
        import uuid
        return str(uuid.uuid4())

    def validate_user_data(self, username, email, password, age, phone=None, address=None):
        errors = []
        user_data = {
            "username": username,
            "email": email,
            "password_hash": "",
            "salt": "",
            "age": age,
            "phone": phone,
            "address": address,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "failed_attempts": 0,
            "locked": False,
        }

        # Username validation
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters")
        if len(username) > 50:
            errors.append("Username must be less than 50 characters")
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append("Username can only contain letters, numbers, and underscores")
        if user_data["username"] in self.db.data:
            errors.append("Username already exists")

        # Email validation
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("Invalid email address")

        # Password validation with deep nesting
        if password:
            if len(password) < 8:
                errors.append(f"Password must be at least {8} characters")
            else:
                has_upper = False
                has_lower = False
                has_digit = False
                has_special = False
                for char in password:
                    if char.isupper():
                        has_upper = True
                    elif char.islower():
                        has_lower = True
                    elif char.isdigit():
                        has_digit = True
                    else:
                        has_special = True

                if not has_upper:
                    errors.append("Password must contain an uppercase letter")
                if not has_lower:
                    errors.append("Password must contain a lowercase letter")
                if not has_digit:
                    errors.append("Password must contain a digit")
                if not has_special:
                    errors.append("Password must contain a special character")
        else:
            errors.append("Password is required")

        # Age validation
        if age is not None:
            if not isinstance(age, int) or age < 13 or age > 120:
                errors.append("Age must be between 13 and 120")

        # Phone validation
        if phone:
            cleaned = re.sub(r'[\s\-\(\)]', '', phone)
            if not re.match(r'^\+?[0-9]{10,15}$', cleaned):
                errors.append("Invalid phone number")

        return errors

    def create_user(self, username, email, password, age, phone=None, address=None):
        errors = self.validate_user_data(username, email, password, age, phone, address)
        if errors:
            return {"success": False, "errors": errors}

        import uuid
        salt = str(uuid.uuid4())[:8]
        password_hash = self._hash_password(password, salt)

        user_data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "salt": salt,
            "age": age,
            "phone": phone,
            "address": address,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "failed_attempts": 0,
            "locked": False,
        }

        self.db.set(username, user_data)
        self._save_to_disk()

        # Send welcome email
        self._send_notification(
            username,
            "Welcome!",
            f"Welcome to our platform, {username}! Your account has been created.",
        )

        return {"success": True, "username": username}

    def get_user(self, username):
        user = self.db.get(username)
        if user:
            safe_user = {k: v for k, v in user.items() if k not in ("password_hash", "salt")}
            return safe_user
        return None

    def update_user(self, username, **updates):
        user = self.db.get(username)
        if not user:
            return {"success": False, "error": "User not found"}

        allowed = {"email", "age", "phone", "address"}
        for key, value in updates.items():
            if key in allowed:
                user[key] = value

        user["updated_at"] = datetime.now().isoformat()
        self._save_to_disk()
        return {"success": True}

    def delete_user(self, username):
        if username in self.db.data:
            del self.db.data[username]
            self._save_to_disk()
            return True
        return False

    def _hash_password(self, password, salt):
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    def _generate_token(self, username):
        import uuid
        return str(uuid.uuid4())

    def _send_notification(self, to, subject, body):
        # Send email notification
        pass  # Implementation not provided

    def _save_to_disk(self):
        try:
            safe_data = {}
            for k, v in self.db.data.items():
                safe_data[k] = {dk: dv for dk, dv in v.items()}
            with open("users.json", "w") as f:
                json.dump(safe_data, f, indent=2, default=str)
        except Exception:
            pass  # Silently fail - bad practice


class UserService:
    def __init__(self, db_path=None, smtp_host=None, smtp_port=587):
        self.auth_service = AuthService(db_path, smtp_host, smtp_port)
        self.max_login_attempts = 5
        self.password_min_length = 8
        self.token_expiry_hours = 24
        self.session_tokens = {}

    def authenticate(self, username, password):
        return self.auth_service.authenticate(username, password)

    def validate_token(self, token):
        return self.auth_service.validate_token(token)

    def logout(self, token):
        return self.auth_service.logout(token)

    def create_user(self, username, email, password, age, phone=None, address=None):
        return self.auth_service.create_user(username, email, password, age, phone, address)

    def get_user(self, username):
        return self.auth_service.get_user(username)

    def update_user(self, username, **updates):
        return self.auth_service.update_user(username, **updates)

    def delete_user(self, username):
        return self.auth_service.delete_user(username)