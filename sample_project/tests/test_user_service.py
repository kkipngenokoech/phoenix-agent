import pytest
from application import Application, AuthService, UserServiceImpl, Database, EmailLog, NotificationService


@pytest.fixture
def auth_service():
    return Application().auth_service


@pytest.fixture
def user_service(auth_service):
    return Application().user_service


@pytest.fixture
def notification_service():
    return Application().notification_service


class TestAuthService:
    def test_authenticate_valid_credentials(self, auth_service):
        token = auth_service.authenticate("test_user", "password")
        assert token

    def test_authenticate_invalid_password(self, auth_service):
        with pytest.raises(Exception):
            auth_service.authenticate("test_user", "wrong_password")

    def test_validate_token_valid_token(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        assert user_service.validate_token(token)

    def test_validate_token_invalid_token(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.validate_token("invalid_token")

    def test_logout_valid_token(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        assert user_service.logout(token)

    def test_logout_invalid_token(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.logout("invalid_token")


class TestUserService:
    def test_create_user_valid_credentials(self, user_service):
        result = user_service.create_user("test_user", "password", 25)
        assert result["success"] is True

    def test_create_user_invalid_password(self, user_service):
        with pytest.raises(Exception):
            user_service.create_user("test_user", "wrong_password", 25)

    def test_get_user_valid_username(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        result = user_service.get_user(token)
        assert result

    def test_get_user_invalid_username(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.get_user("invalid_token")

    def test_update_user_valid_username(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        result = user_service.update_user(token, email="new_email@example.com")
        assert result["success"] is True

    def test_update_user_invalid_username(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.update_user("invalid_token", email="new_email@example.com")

    def test_delete_user_valid_username(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        result = user_service.delete_user(token)
        assert result

    def test_delete_user_invalid_username(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.delete_user("invalid_token")


class TestDatabase:
    def test_save_to_disk_valid_data(self, Database):
        data = {"key": "value"}
        db = Database()
        db.save_to_disk("test.json")
        assert os.path.exists("test.json")

    def test_save_to_disk_invalid_data(self, Database):
        with pytest.raises(Exception):
            Database().save_to_disk("invalid.json")


class TestEmailLog:
    def test_append_record_valid_record(self, EmailLog):
        record = {"to": "test@example.com"}
        email_log = EmailLog()
        email_log.append(record)
        assert len(email_log.records) == 1

    def test_get_history_valid_username(self, EmailLog):
        record = {"to": "test@example.com"}
        email_log = EmailLog()
        email_log.append(record)
        result = email_log.get_history("test@example.com")
        assert len(result) == 1

    def test_get_history_invalid_username(self, EmailLog):
        with pytest.raises(Exception):
            EmailLog().get_history("invalid_email")


class TestNotificationService:
    def test_send_notification_valid_subject_and_body(self, NotificationService):
        notification_service = NotificationService()
        result = notification_service.send_notification("test@example.com", "Test Subject", "Test Body")
        assert result

    def test_send_notification_invalid_subject_or_body(self, NotificationService):
        with pytest.raises(Exception):
            NotificationService().send_notification("test@example.com", "", "")


class TestApplication:
    def test_create_auth_service_valid_credentials(self, Application):
        auth_service = Application().auth_service
        token = auth_service.authenticate("test_user", "password")
        assert token

    def test_create_auth_service_invalid_password(self, Application):
        with pytest.raises(Exception):
            Application().auth_service.authenticate("test_user", "wrong_password")

    def test_create_user_service_valid_credentials(self, user_service):
        result = user_service.create_user("test_user", "password", 25)
        assert result["success"] is True

    def test_create_user_service_invalid_password(self, user_service):
        with pytest.raises(Exception):
            user_service.create_user("test_user", "wrong_password", 25)

    def test_get_user_service_valid_username(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        result = user_service.get_user(token)
        assert result

    def test_get_user_service_invalid_username(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.get_user("invalid_token")

    def test_update_user_service_valid_username(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        result = user_service.update_user(token, email="new_email@example.com")
        assert result["success"] is True

    def test_update_user_service_invalid_username(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.update_user("invalid_token", email="new_email@example.com")

    def test_delete_user_service_valid_username(self, auth_service, user_service):
        token = user_service.authenticate("test_user", "password")
        result = user_service.delete_user(token)
        assert result

    def test_delete_user_service_invalid_username(self, auth_service, user_service):
        with pytest.raises(Exception):
            user_service.delete_user("invalid_token")