from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Pet(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female")]
    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("RESERVED", "Reserved"),
        ("ADOPTED", "Adopted/Sold"),
    ]

    name = models.CharField(max_length=100)
    species = models.CharField(max_length=50)  # e.g., Dog, Cat, Bird
    breed = models.CharField(max_length=100)
    age_months = models.PositiveIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_vaccinated = models.BooleanField(default=False)
    medical_notes = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="AVAILABLE")
    image = models.ImageField(upload_to="pets/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.species} - {self.breed})"


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    brand = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("SHIPPED", "Shipped"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
    ]

    customer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="orders")
    shipping_address = models.TextField()
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDING")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    pet = models.ForeignKey(Pet, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        item_name = self.product.name if self.product else self.pet.name
        return f"{self.quantity}x {item_name} (Order #{self.order.id})"
