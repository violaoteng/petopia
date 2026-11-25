from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import (
    ForgotPasswordForm,
    OtpVerifyForm,
    ResetPasswordWithOtpForm,
    UserRegisterForm,
)
from .models import OtpCode, Profile

User = get_user_model()

PENDING_VERIFY_SESSION_KEY = 'pending_verify_user_id'
PENDING_RESET_SESSION_KEY = 'pending_reset_user_id'


def _get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _send_otp_email(user, otp_obj, purpose_label):
    recipient = (user.email or '').strip()
    if not recipient:
        return False

    subject = f'Petopia — {purpose_label} Code'
    message = (
        f'Hi {user.get_username()},\n\n'
        f'Your 6-digit Petopia {purpose_label.lower()} code is: {otp_obj.code}\n'
        f'This code expires in 10 minutes.\n\n'
        f'If you did not request this, you can safely ignore this email.'
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[recipient],
        fail_silently=False,
    )
    return True


def _resolve_target_user(request, session_key):
    if request.user.is_authenticated:
        return request.user

    user_id = request.session.get(session_key)
    if not user_id:
        return None

    return User.objects.filter(pk=user_id).first()


def get_started(request):
    if request.user.is_authenticated:
        return redirect('users:profile')
    return render(request, 'users/get_started.html')


class UserLoginView(LoginView):
    template_name = 'users/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return next_url
        return reverse_lazy('users:profile')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Welcome back, {self.request.user.get_username()}!')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username or password.')
        return super().form_invalid(form)


class UserLogoutView(LogoutView):
    next_page = reverse_lazy('users:get_started')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and request.user.is_authenticated:
            messages.info(request, 'You have been logged out.')
        return super().dispatch(request, *args, **kwargs)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('users:profile')

    next_url = request.POST.get('next') or request.GET.get('next') or ''

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_username()}!')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('users:profile')
        messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm(request)

    return render(
        request,
        'users/login.html',
        {
            'form': form,
            'next': next_url,
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect('users:profile')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            otp_obj = OtpCode.issue(user, OtpCode.Purpose.VERIFY_ACCOUNT)
            sent = _send_otp_email(user, otp_obj, 'Account Verification')
            request.session[PENDING_VERIFY_SESSION_KEY] = user.pk

            if sent:
                messages.success(
                    request,
                    'Account created! We sent a 6-digit verification code to your email.',
                )
            else:
                messages.warning(
                    request,
                    'Account created, though no email address was set. Use the verification code issued to finish setup.',
                )
            return redirect('users:verify_otp')
        messages.error(request, 'Please fix the errors below to create your account.')
    else:
        form = UserRegisterForm()

    return render(request, 'users/register.html', {'form': form})


def verify_otp(request):
    target_user = _resolve_target_user(request, PENDING_VERIFY_SESSION_KEY)
    if target_user is None:
        messages.info(request, 'Start by registering or logging in to verify your account.')
        return redirect('users:get_started')

    profile = _get_or_create_profile(target_user)

    if request.method == 'POST':
        form = OtpVerifyForm(request.POST)
        if form.is_valid():
            raw_code = form.cleaned_data['code']
            latest_otp = OtpCode.objects.filter(
                user=target_user,
                purpose=OtpCode.Purpose.VERIFY_ACCOUNT,
                is_used=False,
            ).first()

            if latest_otp and latest_otp.is_valid(raw_code):
                latest_otp.mark_used()
                profile.is_email_verified = True
                profile.save(update_fields=['is_email_verified', 'updated_at'])
                request.session.pop(PENDING_VERIFY_SESSION_KEY, None)

                if not request.user.is_authenticated:
                    login(request, target_user)

                messages.success(request, 'Your email address is now verified!')
                return redirect('users:profile')

            form.add_error('code', 'Invalid or expired OTP code.')
            messages.error(request, 'That OTP code is invalid or has expired.')
    else:
        form = OtpVerifyForm()

    return render(
        request,
        'users/verify_otp.html',
        {
            'form': form,
            'target_user': target_user,
            'is_verified': profile.is_email_verified,
        },
    )


@require_POST
def resend_otp(request):
    target_user = _resolve_target_user(request, PENDING_VERIFY_SESSION_KEY)
    if target_user is None:
        messages.info(request, 'No pending verification session was found.')
        return redirect('users:get_started')

    otp_obj = OtpCode.issue(target_user, OtpCode.Purpose.VERIFY_ACCOUNT)
    request.session[PENDING_VERIFY_SESSION_KEY] = target_user.pk
    sent = _send_otp_email(target_user, otp_obj, 'Account Verification')

    if sent:
        messages.success(request, 'A fresh 6-digit verification OTP has been sent.')
    else:
        messages.warning(request, 'A fresh 6-digit verification OTP has been issued.')

    return redirect('users:verify_otp')


def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip()
            user = User.objects.filter(email__iexact=email).first()

            if user:
                otp_obj = OtpCode.issue(user, OtpCode.Purpose.PASSWORD_RESET)
                _send_otp_email(user, otp_obj, 'Password Reset')
                request.session[PENDING_RESET_SESSION_KEY] = user.pk

            messages.info(
                request,
                'If an account matches that email, a 6-digit password reset code has been sent.',
            )
            return redirect('users:reset_password')
    else:
        form = ForgotPasswordForm()

    return render(request, 'users/forgot_password.html', {'form': form})


def reset_password(request):
    user_id = request.session.get(PENDING_RESET_SESSION_KEY)
    target_user = User.objects.filter(pk=user_id).first() if user_id else None

    if target_user is None:
        messages.info(request, 'Enter your email first to receive a password reset OTP.')
        return redirect('users:forgot_password')

    if request.method == 'POST':
        form = ResetPasswordWithOtpForm(request.POST, user=target_user)
        if form.is_valid():
            raw_code = form.cleaned_data['code']
            new_password = form.cleaned_data['new_password1']

            latest_otp = OtpCode.objects.filter(
                user=target_user,
                purpose=OtpCode.Purpose.PASSWORD_RESET,
                is_used=False,
            ).first()

            if latest_otp and latest_otp.is_valid(raw_code):
                latest_otp.mark_used()
                target_user.set_password(new_password)
                target_user.save()
                request.session.pop(PENDING_RESET_SESSION_KEY, None)
                messages.success(request, 'Password updated! You can now log in.')
                return redirect('users:login')

            form.add_error('code', 'Invalid or expired reset OTP code.')
            messages.error(request, 'That reset OTP code is invalid or has expired.')
    else:
        form = ResetPasswordWithOtpForm(user=target_user)

    return render(
        request,
        'users/reset_password.html',
        {
            'form': form,
            'target_user': target_user,
        },
    )


@login_required
def profile(request):
    user_profile = _get_or_create_profile(request.user)

    class UserAccountForm(UserChangeForm):
        password = None

        class Meta:
            model = User
            fields = ('first_name', 'last_name', 'email')

    class ProfileDetailsForm(UserChangeForm):
        class Meta:
            model = Profile
            fields = ('phone_number', 'address')

    if request.method == 'POST':
        user_form = UserAccountForm(request.POST, instance=request.user)
        profile_form = ProfileDetailsForm(request.POST, instance=user_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile details updated.')
            return redirect('users:profile')
        messages.error(request, 'Please check the highlighted profile fields.')
    else:
        user_form = UserAccountForm(instance=request.user)
        profile_form = ProfileDetailsForm(instance=user_profile)

    orders = []
    if hasattr(request.user, 'orders'):
        orders = request.user.orders.all().order_by('-created_at')

    return render(
        request,
        'users/profile.html',
        {
            'user_profile': user_profile,
            'user_form': user_form,
            'profile_form': profile_form,
            'orders': orders,
        },
    )


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('users:get_started')
