from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name_plural': 'Categories',
            },
        ),
        migrations.CreateModel(
            name='Pet',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100)),
                ('species', models.CharField(max_length=50)),
                ('breed', models.CharField(max_length=100)),
                ('age_months', models.PositiveIntegerField()),
                ('gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female')], max_length=1)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_vaccinated', models.BooleanField(default=False)),
                ('medical_notes', models.TextField(blank=True)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('AVAILABLE', 'Available'),
                            ('RESERVED', 'Reserved'),
                            ('ADOPTED', 'Adopted/Sold'),
                        ],
                        default='AVAILABLE',
                        max_length=15,
                    ),
                ),
                ('image', models.ImageField(blank=True, null=True, upload_to='pets/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=150)),
                ('slug', models.SlugField(unique=True)),
                ('description', models.TextField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stock', models.PositiveIntegerField(default=0)),
                ('brand', models.CharField(blank=True, max_length=100)),
                ('image', models.ImageField(blank=True, null=True, upload_to='products/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'category',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='products',
                        to='myapp.category',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('shipping_address', models.TextField()),
                ('phone_number', models.CharField(max_length=20)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('PENDING', 'Pending'),
                            ('PAID', 'Paid'),
                            ('SHIPPED', 'Shipped'),
                            ('DELIVERED', 'Delivered'),
                            ('CANCELLED', 'Cancelled'),
                        ],
                        default='PENDING',
                        max_length=15,
                    ),
                ),
                (
                    'total_amount',
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'customer',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='orders',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('price_at_purchase', models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='items',
                        to='myapp.order',
                    ),
                ),
                (
                    'pet',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to='myapp.pet',
                    ),
                ),
                (
                    'product',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to='myapp.product',
                    ),
                ),
            ],
        ),
    ]
