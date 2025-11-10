# validators.py
import re
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Common weak passwords to reject
COMMON_PASSWORDS = {
    "password", "123456", "12345678", "123456789", "qwerty",
    "abc123", "password1", "admin", "welcome", "monkey"
}


def validate_password(password: str) -> list[str]:
    """Validate password against strength requirements with security checks"""
    errors = []

    # Length checks
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f'Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long')

    if len(password) > 256:  # Prevent extremely long passwords (DoS protection)
        errors.append('Password must be less than 256 characters')

    # Common password check
    if password.lower() in COMMON_PASSWORDS:
        errors.append('Password is too common and easily guessable')

    # Character type requirements
    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append('Password must contain at least one uppercase letter')

    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append('Password must contain at least one lowercase letter')

    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        errors.append('Password must contain at least one digit')

    if settings.PASSWORD_REQUIRE_NON_ALPHANUMERIC and not any(not c.isalnum() for c in password):
        errors.append('Password must contain at least one non-alphanumeric character')

    # Sequential character check (e.g., "123", "abc")
    if has_sequential_chars(password, 3):
        errors.append('Password contains sequential characters')

    # Repeated character check
    if has_repeated_chars(password, 4):
        errors.append('Password contains too many repeated characters')

    return errors


def has_sequential_chars(text: str, length: int) -> bool:
    """Check for sequential characters"""
    for i in range(len(text) - length + 1):
        segment = text[i:i + length]
        if is_sequential(segment):
            return True
    return False


def is_sequential(segment: str) -> bool:
    """Check if segment is sequential (numbers or letters)"""
    if segment.isdigit():
        return segment in '0123456789' or segment in '9876543210'
    elif segment.isalpha() and segment.islower():
        return segment in 'abcdefghijklmnopqrstuvwxyz' or segment in 'zyxwvutsrqponmlkjihgfedcba'
    elif segment.isalpha() and segment.isupper():
        return segment in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' or segment in 'ZYXWVUTSRQPONMLKJIHGFEDCBA'
    return False


def has_repeated_chars(text: str, max_repeat: int) -> bool:
    """Check for repeated characters"""
    count = 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1]:
            count += 1
            if count > max_repeat:
                return True
        else:
            count = 1
    return False


def validate_username(username: str) -> list[str]:
    """Validate username format with security considerations"""
    errors = []

    if len(username) < 3:
        errors.append('Username must be at least 3 characters long')

    if len(username) > 50:
        errors.append('Username must be less than 50 characters')

    # Allow only specific characters
    if not re.match(r'^[a-zA-Z0-9\-._@+]+$', username):
        errors.append('Username can only contain letters, numbers, and -._@+ characters')

    # Prevent reserved usernames
    reserved_names = {'admin', 'administrator', 'root', 'system', 'api', 'webmaster'}
    if username.lower() in reserved_names:
        errors.append('This username is reserved')

    # Prevent potentially confusing usernames
    if re.match(r'^\d+$', username):  # All numbers
        errors.append('Username cannot consist only of numbers')

    return errors


def validate_email(email: str) -> list[str]:
    """Basic email validation"""
    errors = []

    if len(email) > 254:  # RFC 5321 limit
        errors.append('Email address too long')

    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        errors.append('Invalid email format')

    return errors