import uuid

from django.db import models


class MpesaPayment(models.Model):
    class Status(models.TextChoices):
        INITIATING = 'INITIATING', 'Initiating'
        PENDING = 'PENDING', 'Pending'
        SUCCEEDED = 'SUCCEEDED', 'Succeeded'
        FAILED = 'FAILED', 'Failed'
        UNKNOWN = 'UNKNOWN', 'Unknown; reconcile before retrying'

    order = models.ForeignKey(
        'myapp.Order',
        on_delete=models.PROTECT,
        related_name='mpesa_payments',
    )
    phone_number = models.CharField(max_length=12)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.INITIATING,
    )
    callback_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, unique=True, null=True)
    mpesa_receipt_number = models.CharField(max_length=32, blank=True)
    result_code = models.CharField(max_length=32, blank=True)
    result_description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'M-Pesa payment for order #{self.order_id} ({self.status})'
