from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path(
        'orders/<int:order_id>/stk-push/',
        views.start_stk_push,
        name='start-stk-push',
    ),
    path(
        '<int:payment_id>/status/',
        views.payment_status,
        name='payment-status',
    ),
    path(
        'callbacks/mpesa/<uuid:callback_token>/',
        views.mpesa_callback,
        name='mpesa-callback',
    ),
]
