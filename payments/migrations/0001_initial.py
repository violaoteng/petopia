import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('myapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MpesaPayment',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('phone_number', models.CharField(max_length=12)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('INITIATING', 'Initiating'),
                            ('PENDING', 'Pending'),
                            ('SUCCEEDED', 'Succeeded'),
                            ('FAILED', 'Failed'),
                            ('UNKNOWN', 'Unknown; reconcile before retrying'),
                        ],
                        default='INITIATING',
                        max_length=10,
                    ),
                ),
                (
                    'callback_token',
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ('merchant_request_id', models.CharField(blank=True, max_length=100)),
                (
                    'checkout_request_id',
                    models.CharField(blank=True, max_length=100, null=True, unique=True),
                ),
                ('mpesa_receipt_number', models.CharField(blank=True, max_length=32)),
                ('result_code', models.CharField(blank=True, max_length=32)),
                ('result_description', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='mpesa_payments',
                        to='myapp.order',
                    ),
                ),
            ],
        ),
    ]
