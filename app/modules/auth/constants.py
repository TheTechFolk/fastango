# app/modules/auth/constants.py

# ── Success Messages ──────────────────────────────────────────────────────────
REGISTER_SUCCESS_MSG = "Account created successfully."
LOGIN_SUCCESS_MSG = "Login successful."
REFRESH_SUCCESS_MSG = "Token refreshed successfully."
ME_SUCCESS_MSG = "Account details retrieved successfully."

# ── Error Messages ────────────────────────────────────────────────────────────
# Generic credentials message — covers "user not found", "wrong password" and
# "account disabled" alike, so the response cannot enumerate registered accounts.
INVALID_CREDENTIALS_MSG = "Invalid email or password."
# Generic registration failure — does not confirm whether the email is already
# registered, limiting enumeration via the public registration endpoint.
EMAIL_TAKEN_MSG = "Unable to register with the provided credentials."
INVALID_REFRESH_MSG = "Invalid or expired refresh token."
REGISTRATION_DISABLED_MSG = "Registration is currently closed."
