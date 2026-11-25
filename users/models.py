import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    is_email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_username()} profile'


class OtpCode(models.Model):
    class Purpose(models.TextChoices):
        VERIFY_ACCOUNT = 'VERIFY_ACCOUNT', 'Account / Email Verification'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Forgot Password Reset'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='otp_codes',
    )
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
    )
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    @classmethod
    def issue(cls, user, purpose, ttl_minutes=10):
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        code = f'{secrets.randbelow(1_000_000):06d}'
        return cls.objects.create(
            user=user,
            purpose=purpose,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def is_valid(self, raw_code):
        if self.is_used or self.is_expired:
            return False
        return secrets.compare_digest(self.code, (raw_code or '').strip())

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])

    def __str__(self):
        return f'{self.user.get_username()} - {self.purpose} ({self.code})'