# app/modules/auth/constants.py

# ── Success Messages ──────────────────────────────────────────────────────────
ADMIN_REGISTER_SUCCESS_MSG = "Admin account created successfully."
ADMIN_LOGIN_SUCCESS_MSG = "Admin login successful."
ADMIN_LOGOUT_SUCCESS_MSG = "Admin logged out successfully."
TOKEN_REFRESH_SUCCESS_MSG = "Token refreshed successfully."
PASSWORD_CHANGE_SUCCESS_MSG = "Password changed successfully."

# ── Error Messages ────────────────────────────────────────────────────────────
# Generic credentials message — covers both "user not found" and "wrong password"
# so the response cannot be used to enumerate registered accounts.
INVALID_CREDENTIALS_MSG = "Invalid email or password."
ACCOUNT_INACTIVE_MSG = "This account has been deactivated."
# Generic registration failure — does not confirm whether the email is already
# registered, limiting email-enumeration via the public registration endpoint.
EMAIL_TAKEN_MSG = "Unable to register with the provided credentials."
INVALID_REFRESH_TOKEN_MSG = "Invalid or expired refresh token."
WRONG_CURRENT_PASSWORD_MSG = "Current password is incorrect."
