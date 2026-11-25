# users/admin.py
from django.contrib import admin

from .models import OtpCode, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_email_verified', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'code', 'is_used', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_used')
    search_fields = ('user__username', 'user__email', 'code')
    readonly_fields = ('created_at',)