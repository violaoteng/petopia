document.addEventListener('DOMContentLoaded', () => {
    const EYE_OPEN_SVG = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/>
            <circle cx="12" cy="12" r="3"/>
        </svg>
    `;

    const EYE_OFF_SVG = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>
            <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c6.5 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>
            <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3.5 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>
            <line x1="2" y1="2" x2="22" y2="22"/>
        </svg>
    `;

    document.querySelectorAll('.auth-card input[type="password"], .auth-box input[type="password"]').forEach((input) => {
        if (input.parentElement && input.parentElement.classList.contains('password-field-wrap')) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'password-field-wrap';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'password-toggle-btn';
        toggleBtn.setAttribute('aria-label', 'Show password');
        toggleBtn.setAttribute('aria-pressed', 'false');
        toggleBtn.innerHTML = EYE_OPEN_SVG;

        toggleBtn.addEventListener('click', () => {
            const isHidden = input.type === 'password';
            input.type = isHidden ? 'text' : 'password';
            toggleBtn.innerHTML = isHidden ? EYE_OFF_SVG : EYE_OPEN_SVG;
            toggleBtn.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
            toggleBtn.setAttribute('aria-pressed', String(isHidden));
        });

        wrapper.appendChild(toggleBtn);
    });

    // Restrict 6-digit OTP inputs to digits only
    document.querySelectorAll('input[name="code"]').forEach((otpInput) => {
        otpInput.addEventListener('input', () => {
            otpInput.value = otpInput.value.replace(/\D/g, '').slice(0, 6);
        });
    });

    // Prevent accidental double submissions
    document.querySelectorAll('.auth-card form, .auth-box form').forEach((form) => {
        form.addEventListener('submit', () => {
            const btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.disabled) {
                btn.disabled = true;
                setTimeout(() => {
                    btn.disabled = false;
                }, 4000);
            }
        });
    });
});
