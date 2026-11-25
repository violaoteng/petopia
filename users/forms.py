from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Profile

User = get_user_model()


def _normalize_phone(raw_phone):
    cleaned = ''.join(ch for ch in (raw_phone or '').strip() if ch.isdigit() or ch == '+')
    return cleaned


class UserRegisterForm(UserCreationForm):
    phone_number = forms.CharField(
        label='Phone number',
        max_length=20,
        widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
    )
    email = forms.EmailField(
        label='Email',
        required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].label = 'Password'
        self.fields['password2'].label = 'Confirm password'
        for field in self.fields.values():
            field.help_text = None

    def clean_phone_number(self):
        phone = _normalize_phone(self.cleaned_data.get('phone_number'))
        digits = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits) < 9:
            raise forms.ValidationError('Enter a valid phone number.')
        if (
            User.objects.filter(username=phone).exists()
            or Profile.objects.filter(phone_number=phone).exists()
        ):
            raise forms.ValidationError('An account with this phone number already exists.')
        return phone

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        phone = self.cleaned_data['phone_number']
        user = super().save(commit=False)
        user.username = phone
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone_number = phone
            profile.save(update_fields=['phone_number', 'updated_at'])
        return user


class PhoneAuthenticationForm(forms.Form):
    phone_number = forms.CharField(
        label='Phone number',
        max_length=20,
        widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        raw_phone = cleaned.get('phone_number')
        password = cleaned.get('password')

        if raw_phone and password:
            phone = _normalize_phone(raw_phone)
            target = (
                User.objects.filter(username=phone).first()
                or User.objects.filter(username=raw_phone.strip()).first()
            )
            if target is None:
                matched_profile = Profile.objects.select_related('user').filter(phone_number=phone).first()
                if matched_profile:
                    target = matched_profile.user

            username_to_auth = target.username if target else phone
            self.user_cache = authenticate(
                self.request,
                username=username_to_auth,
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError('Invalid phone number or password.')
            if not self.user_cache.is_active:
                raise forms.ValidationError('This account is inactive.')

        return cleaned

    def get_user(self):
        return self.user_cache


class OtpVerifyForm(forms.Form):
    code = forms.CharField(
        label='Verification code',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}),
    )

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError('Enter a valid 6-digit code.')
        return code


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),
    )

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()


class ResetPasswordWithOtpForm(forms.Form):
    code = forms.CharField(
        label='Reset code',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}),
    )
    new_password1 = forms.CharField(
        label='New password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        label='Confirm new password',
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError('Enter a valid 6-digit code.')
        return code

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get('new_password1')
        pw2 = cleaned.get('new_password2')
        if pw1 and pw2 and pw1 != pw2:
            self.add_error('new_password2', 'Passwords do not match.')
        return cleaned
