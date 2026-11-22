import json
import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from myapp.models import Order

from .models import MpesaPayment
from .services import (
    MpesaAPIError,
    MpesaConfigurationError,
    MpesaTransportError,
    initiate_stk_push,
    normalize_phone_number,
    validate_mpesa_configuration,
)

logger = logging.getLogger(__name__)


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


@require_POST
@login_required
def start_stk_push(request, order_id):
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    try:
        validate_mpesa_configuration()
    except MpesaConfigurationError:
        logger.exception('M-Pesa payment configuration is incomplete.')
        return JsonResponse(
            {'error': 'M-Pesa is not configured yet.'},
            status=503,
        )

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.status != 'PENDING':
            return JsonResponse(
                {'error': 'This order is not awaiting payment.'},
                status=409,
            )
        try:
            phone_number = normalize_phone_number(locked_order.phone_number)
            amount = Decimal(locked_order.total_amount)
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        if amount <= 0 or amount != amount.to_integral_value():
            return JsonResponse(
                {'error': 'The order total must be a positive whole-shilling amount.'},
                status=400,
            )

        active_payment = MpesaPayment.objects.filter(
            order=locked_order,
            status__in=[
                MpesaPayment.Status.INITIATING,
                MpesaPayment.Status.PENDING,
                MpesaPayment.Status.UNKNOWN,
            ],
        ).exists()
        if active_payment:
            return JsonResponse(
                {'error': 'A payment attempt is already in progress or needs reconciliation.'},
                status=409,
            )

        payment = MpesaPayment.objects.create(
            order=locked_order,
            phone_number=phone_number,
            amount=amount,
        )

    try:
        response = initiate_stk_push(payment)
    except MpesaAPIError as exc:
        with transaction.atomic():
            payment = MpesaPayment.objects.select_for_update().get(pk=payment.pk)
            if payment.status == MpesaPayment.Status.INITIATING:
                payment.status = MpesaPayment.Status.FAILED
                payment.completed_at = timezone.now()
                payment.result_description = str(exc)[:255]
                payment.save(
                    update_fields=[
                        'status',
                        'result_description',
                        'completed_at',
                        'updated_at',
                    ]
                )
            elif payment.status not in (
                MpesaPayment.Status.SUCCEEDED,
                MpesaPayment.Status.FAILED,
            ):
                payment.status = MpesaPayment.Status.UNKNOWN
                payment.result_description = (
                    'Initiation response conflicted with callback state; reconcile before retrying.'
                )
                payment.save(update_fields=['status', 'result_description', 'updated_at'])
        if payment.status == MpesaPayment.Status.SUCCEEDED:
            return JsonResponse(
                {'payment_id': payment.pk, 'status': payment.status},
                status=202,
            )
        return JsonResponse({'error': str(exc)}, status=502)
    except MpesaTransportError:
        logger.exception('M-Pesa STK request outcome is uncertain for payment %s.', payment.pk)
        with transaction.atomic():
            payment = MpesaPayment.objects.select_for_update().get(pk=payment.pk)
            if payment.status == MpesaPayment.Status.INITIATING:
                payment.status = MpesaPayment.Status.UNKNOWN
                payment.result_description = (
                    'Daraja response was not received; reconcile before retrying.'
                )
                payment.save(update_fields=['status', 'result_description', 'updated_at'])
            elif payment.status == MpesaPayment.Status.PENDING:
                return JsonResponse(
                    {
                        'payment_id': payment.pk,
                        'status': payment.status,
                        'message': 'STK Push sent; waiting for customer confirmation.',
                    },
                    status=202,
                )
            elif payment.status == MpesaPayment.Status.SUCCEEDED:
                return JsonResponse(
                    {'payment_id': payment.pk, 'status': payment.status},
                    status=202,
                )
        return JsonResponse(
            {
                'error': (
                    'Daraja did not confirm the request. Check the payment status before retrying.'
                ),
                'payment_id': payment.pk,
            },
            status=503,
        )

    response_checkout_id = str(response['CheckoutRequestID'])
    with transaction.atomic():
        payment = MpesaPayment.objects.select_for_update().get(pk=payment.pk)
        if payment.checkout_request_id and payment.checkout_request_id != response_checkout_id:
            payment.status = MpesaPayment.Status.UNKNOWN
            payment.result_description = (
                'Daraja response did not match the callback request ID; reconcile before retrying.'
            )
            payment.save(update_fields=['status', 'result_description', 'updated_at'])
            logger.error('M-Pesa request ID mismatch for payment %s.', payment.pk)
            return JsonResponse(
                {
                    'error': 'Payment status needs reconciliation before retrying.',
                    'payment_id': payment.pk,
                },
                status=503,
            )

        payment.merchant_request_id = str(response['MerchantRequestID'])
        payment.checkout_request_id = response_checkout_id
        if payment.status == MpesaPayment.Status.INITIATING:
            payment.status = MpesaPayment.Status.PENDING
        if payment.status == MpesaPayment.Status.PENDING:
            payment.result_description = str(
                response.get('CustomerMessage') or response.get('ResponseDescription', '')
            )[:255]
        payment.save(
            update_fields=[
                'merchant_request_id',
                'checkout_request_id',
                'status',
                'result_description',
                'updated_at',
            ]
        )
    return JsonResponse(
        {
            'payment_id': payment.pk,
            'status': payment.status,
            'message': payment.result_description or 'STK Push sent.',
        },
        status=202,
    )


@require_GET
@login_required
def payment_status(request, payment_id):
    payment = get_object_or_404(
        MpesaPayment.objects.select_related('order'),
        pk=payment_id,
        order__customer=request.user,
    )
    return JsonResponse(
        {
            'payment_id': payment.pk,
            'order_id': payment.order_id,
            'status': payment.status,
            'receipt_number': payment.mpesa_receipt_number or None,
            'message': payment.result_description,
        }
    )


def _callback_metadata(callback):
    callback_metadata = callback.get('CallbackMetadata')
    if not isinstance(callback_metadata, dict):
        return {}
    metadata = callback_metadata.get('Item', [])
    if not isinstance(metadata, list):
        return {}
    return {
        item.get('Name'): item.get('Value')
        for item in metadata
        if isinstance(item, dict) and item.get('Name')
    }


@csrf_exempt
@require_POST
def mpesa_callback(request, callback_token):
    try:
        callback_token = UUID(str(callback_token))
    except ValueError:
        return JsonResponse({'error': 'Invalid callback token.'}, status=404)

    payload = _json_body(request)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'Invalid callback body.'}, status=400)

    body = payload.get('Body')
    callback = body.get('stkCallback') if isinstance(body, dict) else None
    if not isinstance(callback, dict):
        return JsonResponse({'error': 'Missing STK callback data.'}, status=400)
    checkout_request_id = callback.get('CheckoutRequestID')
    if not checkout_request_id:
        return JsonResponse({'error': 'Missing checkout request ID.'}, status=400)
    try:
        result_code = int(callback['ResultCode'])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({'error': 'Missing callback result code.'}, status=400)

    with transaction.atomic():
        payment = (
            MpesaPayment.objects.select_for_update()
            .select_related('order')
            .filter(callback_token=callback_token)
            .first()
        )
        if payment is None:
            logger.warning('Ignoring callback for an unknown M-Pesa payment.')
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback ignored.'})
        if not payment.checkout_request_id:
            payment.checkout_request_id = str(checkout_request_id)
            payment.merchant_request_id = str(callback.get('MerchantRequestID', ''))
            if payment.status in (
                MpesaPayment.Status.INITIATING,
                MpesaPayment.Status.UNKNOWN,
            ):
                payment.status = MpesaPayment.Status.PENDING
            payment.save(
                update_fields=[
                    'checkout_request_id',
                    'merchant_request_id',
                    'status',
                    'updated_at',
                ]
            )
        elif payment.checkout_request_id != checkout_request_id:
            logger.warning('Ignoring callback with a mismatched request ID for payment %s.', payment.pk)
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback ignored.'})

        if payment.status in (MpesaPayment.Status.SUCCEEDED, MpesaPayment.Status.FAILED):
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback already processed.'})

        payment.result_code = str(result_code)
        payment.result_description = str(callback.get('ResultDesc', ''))[:255]
        payment.completed_at = timezone.now()

        if result_code != 0:
            payment.status = MpesaPayment.Status.FAILED
            payment.save(
                update_fields=[
                    'status',
                    'result_code',
                    'result_description',
                    'completed_at',
                    'updated_at',
                ]
            )
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback processed.'})

        metadata = _callback_metadata(callback)
        try:
            callback_amount = Decimal(str(metadata['Amount']))
            callback_phone = normalize_phone_number(str(metadata['PhoneNumber']))
            receipt_value = metadata['MpesaReceiptNumber']
            if receipt_value is None:
                raise ValueError('Missing M-Pesa receipt number.')
            receipt_number = str(receipt_value).strip()
        except (KeyError, TypeError, ValueError, InvalidOperation):
            payment.status = MpesaPayment.Status.UNKNOWN
            payment.result_description = 'Successful callback was missing valid payment details.'
            payment.save(
                update_fields=[
                    'status',
                    'result_code',
                    'result_description',
                    'completed_at',
                    'updated_at',
                ]
            )
            logger.error('M-Pesa callback metadata validation failed for payment %s.', payment.pk)
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback received.'})

        if (
            callback_amount != payment.amount
            or callback_phone != payment.phone_number
            or not receipt_number
        ):
            payment.status = MpesaPayment.Status.UNKNOWN
            payment.result_description = 'Successful callback did not match the pending payment.'
            payment.save(
                update_fields=[
                    'status',
                    'result_code',
                    'result_description',
                    'completed_at',
                    'updated_at',
                ]
            )
            logger.error('M-Pesa callback did not match payment %s.', payment.pk)
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback received.'})

        payment.status = MpesaPayment.Status.SUCCEEDED
        payment.mpesa_receipt_number = receipt_number[:32]
        payment.save(
            update_fields=[
                'status',
                'result_code',
                'result_description',
                'mpesa_receipt_number',
                'completed_at',
                'updated_at',
            ]
        )
        if payment.order.status == 'PENDING':
            payment.order.status = 'PAID'
            payment.order.save(update_fields=['status'])
        else:
            logger.error(
                'Payment %s succeeded while order %s was %s.',
                payment.pk,
                payment.order_id,
                payment.order.status,
            )

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Callback processed.'})
