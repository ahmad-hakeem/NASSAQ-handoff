# Password Reset System Design

## Overview
Two-path password reset: (1) self-service via email with Resend, (2) admin-initiated reset.

## Backend
- `POST /auth/forgot-password` — accepts email, generates JWT reset token (1hr expiry), sends email via Resend
- `POST /auth/reset-password` — accepts token + new_password, validates, resets password
- `backend/engines/email_service.py` — Resend wrapper for sending templated emails
- Security: single-use tokens, generic response ("if email exists, we sent a link"), password complexity validation

## Frontend
- `/forgot-password` page — email input form, bilingual (AR/EN), matches LoginPage design
- `/reset-password?token=xxx` page — new password + confirm form, validates complexity, redirects to login on success
- Both pages are public routes (no auth required)

## Admin Reset Enhancement
- Existing `POST /users/{user_id}/reset-password` already works
- Add email notification to user when admin resets their password

## Email Template
- Arabic-first branded email with NASSAQ logo
- Contains reset link pointing to `{APP_URL}/reset-password?token=xxx`
- Expires in 1 hour warning

## Token Strategy
- JWT with `sub=user_id`, `purpose=password_reset`, `exp=1hr`
- Stored hash in DB for single-use validation
- Invalidated after use or expiry
