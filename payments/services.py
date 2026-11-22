import base64
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse


class MpesaError(Exception):
    pass


class MpesaConfigurationError(MpesaError):
    pass


class MpesaAPIError(MpesaError):
    pass


class MpesaTransportError(MpesaError):
    pass


def normalize_phone_number(value):
    digits = re.sub(r'[\s()+-]', '', value)
    if digits.startswith('0'):
        digits = f'254{digits[1:]}'
    if not re.fullmatch(r'254[17]\d{8}', digits):
        raise ValueError('Enter a valid Kenyan mobile number, such as 0712345678.')
    return digits


def _configuration():
    environment = settings.MPESA_ENVIRONMENT
    if environment == 'sandbox':
        base_url = 'https://sandbox.safaricom.co.ke'
    elif environment == 'production':
        base_url = 'https://api.safaricom.co.ke'
    else:
        raise MpesaConfigurationError('MPESA_ENVIRONMENT must be sandbox or production.')

    required_settings = {
        'MPESA_CONSUMER_KEY': settings.MPESA_CONSUMER_KEY,
        'MPESA_CONSUMER_SECRET': settings.MPESA_CONSUMER_SECRET,
        'MPESA_SHORTCODE': settings.MPESA_SHORTCODE,
        'MPESA_PASSKEY': settings.MPESA_PASSKEY,
        'MPESA_CALLBACK_BASE_URL': settings.MPESA_CALLBACK_BASE_URL,
    }
    missing = [name for name, value in required_settings.items() if not value]
    if missing:
        raise MpesaConfigurationError(
            'Set the Daraja environment variables before requesting payment.'
        )

    callback_url = urlsplit(settings.MPESA_CALLBACK_BASE_URL)
    if callback_url.scheme != 'https' or not callback_url.netloc:
        raise MpesaConfigurationError(
            'MPESA_CALLBACK_BASE_URL must be a public HTTPS origin.'
        )
    if callback_url.path not in ('', '/') or callback_url.query or callback_url.fragment:
        raise MpesaConfigurationError(
            'MPESA_CALLBACK_BASE_URL must contain only the public HTTPS origin.'
        )

    return base_url, required_settings


def validate_mpesa_configuration():
    _configuration()


def _request_json(url, *, method, headers, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read()
    except HTTPError as exc:
        if exc.code >= 500:
            raise MpesaTransportError(
                'Daraja returned a server error; the payment outcome is uncertain.'
            ) from exc
        raise MpesaAPIError(f'Daraja rejected the request (HTTP {exc.code}).') from exc
    except (TimeoutError, URLError) as exc:
        raise MpesaTransportError(
            'Daraja could not be reached; the payment outcome is uncertain.'
        ) from exc

    try:
        result = json.loads(response_body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MpesaTransportError(
            'Daraja returned an unreadable response; the payment outcome is uncertain.'
        ) from exc
    if not isinstance(result, dict):
        raise MpesaTransportError(
            'Daraja returned an unexpected response; the payment outcome is uncertain.'
        )
    return result


def _get_access_token(base_url, credentials):
    auth_value = base64.b64encode(
        f"{credentials['MPESA_CONSUMER_KEY']}:{credentials['MPESA_CONSUMER_SECRET']}".encode(
            'utf-8'
        )
    ).decode('ascii')
    response = _request_json(
        f'{base_url}/oauth/v1/generate?grant_type=client_credentials',
        method='GET',
        headers={'Authorization': f'Basic {auth_value}'},
    )
    token = response.get('access_token')
    if not token:
        raise MpesaAPIError('Daraja did not return an access token.')
    return token


def initiate_stk_push(payment):
    base_url, credentials = _configuration()
    access_token = _get_access_token(base_url, credentials)
    timestamp = (
        datetime.now(timezone.utc) + timedelta(hours=3)
    ).strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        (
            f"{credentials['MPESA_SHORTCODE']}"
            f"{credentials['MPESA_PASSKEY']}"
            f'{timestamp}'
        ).encode('utf-8')
    ).decode('ascii')

    callback_path = reverse(
        'payments:mpesa-callback',
        kwargs={'callback_token': payment.callback_token},
    )
    callback_url = f"{settings.MPESA_CALLBACK_BASE_URL.rstrip('/')}{callback_path}"

    amount = Decimal(payment.amount)
    if amount <= 0 or amount != amount.to_integral_value():
        raise ValueError('M-Pesa STK Push requires a positive whole-shilling amount.')

    payload = {
        'BusinessShortCode': credentials['MPESA_SHORTCODE'],
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': settings.MPESA_TRANSACTION_TYPE,
        'Amount': int(amount),
        'PartyA': payment.phone_number,
        'PartyB': credentials['MPESA_SHORTCODE'],
        'PhoneNumber': payment.phone_number,
        'CallBackURL': callback_url,
        'AccountReference': f'Petopia{payment.order_id}',
        'TransactionDesc': f'Petopia order {payment.order_id}',
    }
    response = _request_json(
        f'{base_url}/mpesa/stkpush/v1/processrequest',
        method='POST',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        payload=payload,
    )

    if str(response.get('ResponseCode')) != '0':
        description = response.get('ResponseDescription', 'Daraja rejected the STK request.')
        raise MpesaAPIError(str(description)[:255])
    if not response.get('CheckoutRequestID') or not response.get('MerchantRequestID'):
        raise MpesaTransportError(
            'Daraja accepted the request without returning its tracking IDs.'
        )
    return response
