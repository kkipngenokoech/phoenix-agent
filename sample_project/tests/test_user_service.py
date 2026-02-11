"""Tests for UserService."""

import pytest
from src.user_service import UserService, DATABASE, EMAIL_LOG


@pytest.fixture(autouse=True)
def clean_db():
    """Reset the in-memory database before each test."""
    DATABASE.clear()
    EMAIL_LOG.clear()
    yield
    DATABASE.clear()
    EMAIL_LOG.clear()


@pytest.fixture
def service():
    return UserService()


class TestAuthentication:
    def test_create_and_authenticate(self, service):
        result = service.create_user("alice", "alice@example.com", "Pass123!@", 25)
        assert result["success"] is True

        token = service.authenticate("alice", "Pass123!@")
        assert token is not None
        assert service.validate_token(token)

    def test_authenticate_wrong_password(self, service):
        service.create_user("bob", "bob@example.com", "Secure99!!", 30)
        token = service.authenticate("bob", "wrongpassword")
        assert token is None

    def test_authenticate_nonexistent_user(self, service):
        token = service.authenticate("ghost", "password")
        assert token is None

    def test_logout(self, service):
        service.create_user("carol", "carol@example.com", "MyPass1!!", 28)
        token = service.authenticate("carol", "MyPass1!!")
        assert token is not None
        assert service.logout(token) is True
        assert service.validate_token(token) is False


class TestValidation:
    def test_valid_user_data(self, service):
        errors = service.validate_user_data("newuser", "new@example.com", "Strong1!!", 25)
        assert errors == []

    def test_short_username(self, service):
        errors = service.validate_user_data("ab", "a@b.com", "Strong1!!", 25)
        assert any("at least 3" in e for e in errors)

    def test_invalid_email(self, service):
        errors = service.validate_user_data("user1", "notanemail", "Strong1!!", 25)
        assert any("email" in e.lower() for e in errors)

    def test_weak_password(self, service):
        errors = service.validate_user_data("user2", "u@b.com", "short", 25)
        assert len(errors) > 0

    def test_invalid_age(self, service):
        errors = service.validate_user_data("user3", "u@b.com", "Strong1!!", 5)
        assert any("age" in e.lower() for e in errors)


class TestPersistence:
    def test_create_user(self, service):
        result = service.create_user("dave", "dave@example.com", "DavePass1!", 35)
        assert result["success"] is True
        assert "dave" in DATABASE

    def test_get_user(self, service):
        service.create_user("eve", "eve@example.com", "EvePass1!!", 22)
        user = service.get_user("eve")
        assert user is not None
        assert user["username"] == "eve"
        assert "password_hash" not in user  # Should be filtered

    def test_update_user(self, service):
        service.create_user("frank", "frank@example.com", "FrankP1!!", 40)
        result = service.update_user("frank", email="frank2@example.com")
        assert result["success"] is True
        assert DATABASE["frank"]["email"] == "frank2@example.com"

    def test_delete_user(self, service):
        service.create_user("grace", "grace@example.com", "GraceP1!!", 33)
        assert service.delete_user("grace") is True
        assert "grace" not in DATABASE
