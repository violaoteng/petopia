import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from myapp.models import Order

from .models import MpesaPayment
from .services import normalize_phone_number


class PhoneNumberTests(TestCase):
    def test_normalizes_common_kenyan_number_formats(self):
        self.assertEqual(normalize_phone_number('0712 345 678'), '254712345678')
        self.assertEqual(normalize_phone_number('+254712345678'), '254712345678')

    def test_rejects_non_kenyan_or_invalid_numbers(self):
        with self.assertRaises(ValueError):
            normalize_phone_number('12345')


class MpesaCallbackTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='buyer')
        self.order = Order.objects.create(
            customer=user,
            shipping_address='1 Pet Street',
            phone_number='0712345678',
            total_amount='125.00',
        )
        self.payment = MpesaPayment.objects.create(
            order=self.order,
            phone_number='254712345678',
            amount='125.00',
            status=MpesaPayment.Status.PENDING,
            checkout_request_id='ws_CO_123',
        )
        self.url = reverse(
            'payments:mpesa-callback',
            kwargs={'callback_token': self.payment.callback_token},
        )
        self.callback = {
            'Body': {
                'stkCallback': {
                    'CheckoutRequestID': 'ws_CO_123',
                    'ResultCode': 0,
                    'ResultDesc': 'The service was accepted successfully',
                    'CallbackMetadata': {
                        'Item': [
                            {'Name': 'Amount', 'Value': 125},
                            {'Name': 'MpesaReceiptNumber', 'Value': 'ABC123XYZ'},
                            {'Name': 'PhoneNumber', 'Value': 254712345678},
                        ]
                    },
                }
            }
        }

    def test_successful_callback_pays_order_and_is_idempotent(self):
        first_response = self.client.post(
            self.url,
            data=json.dumps(self.callback),
            content_type='application/json',
        )
        second_response = self.client.post(
            self.url,
            data=json.dumps(self.callback),
            content_type='application/json',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, MpesaPayment.Status.SUCCEEDED)
        self.assertEqual(self.payment.mpesa_receipt_number, 'ABC123XYZ')
        self.assertEqual(self.order.status, 'PAID')

    def test_callback_with_mismatched_amount_does_not_pay_order(self):
        self.callback['Body']['stkCallback']['CallbackMetadata']['Item'][0]['Value'] = 1

        response = self.client.post(
            self.url,
            data=json.dumps(self.callback),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, MpesaPayment.Status.UNKNOWN)
        self.assertEqual(self.order.status, 'PENDING')

    def test_callback_can_complete_while_stk_response_ids_are_being_saved(self):
        self.payment.checkout_request_id = None
        self.payment.status = MpesaPayment.Status.INITIATING
        self.payment.save(update_fields=['checkout_request_id', 'status', 'updated_at'])

        response = self.client.post(
            self.url,
            data=json.dumps(self.callback),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.checkout_request_id, 'ws_CO_123')
        self.assertEqual(self.payment.status, MpesaPayment.Status.SUCCEEDED)
        self.assertEqual(self.order.status, 'PAID')
