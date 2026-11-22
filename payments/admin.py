from django.contrib import admin
from django.utils import timezone

from .models import MpesaPayment


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'amount',
        'phone_number',
        'status',
        'mpesa_receipt_number',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'order__id',
        'checkout_request_id',
        'merchant_request_id',
        'mpesa_receipt_number',
        'phone_number',
    )
    readonly_fields = (
        'order',
        'phone_number',
        'amount',
        'status',
        'callback_token',
        'merchant_request_id',
        'checkout_request_id',
        'mpesa_receipt_number',
        'result_code',
        'result_description',
        'created_at',
        'updated_at',
        'completed_at',
    )
    actions = ('mark_unknown_as_failed',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(
        description='Mark selected payments failed after verifying no charge'
    )
    def mark_unknown_as_failed(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(
            status__in=[
                MpesaPayment.Status.INITIATING,
                MpesaPayment.Status.UNKNOWN,
                MpesaPayment.Status.PENDING,
            ]
        ).update(
            status=MpesaPayment.Status.FAILED,
            result_description='Manually reconciled: no M-Pesa charge found.',
            completed_at=now,
            updated_at=now,
        )
        self.message_user(
            request,
            f'{updated} payment(s) marked failed. Confirm the Daraja transaction status first.',
        )
