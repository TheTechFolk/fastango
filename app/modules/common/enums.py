# app/modules/common/enums.py
from enum import Enum


class RoleType(str, Enum):
    """User role types across all domains."""

    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"
    VENDOR = "VENDOR"
    PLATFORM = "PLATFORM"


class GenderType(str, Enum):
    """Standardised gender options used in profile modules."""

    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHERS = "OTHERS"
    PREFER_NOT_TO_SAY = "PREFER_NOT_TO_SAY"


class OrderStatus(str, Enum):
    """Lifecycle states of a customer order."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PREPARING = "PREPARING"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class PaymentStatus(str, Enum):
    """Payment transaction states."""

    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PayoutStatus(str, Enum):
    """Vendor payout states."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NotificationType(str, Enum):
    """Types of notifications that can be dispatched to users."""

    PUSH = "PUSH"
    EMAIL = "EMAIL"
    SMS = "SMS"
    IN_APP = "IN_APP"


class ContentType(str, Enum):
    """Content classification for the content management module."""

    BANNER = "BANNER"
    PROMOTION = "PROMOTION"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    FAQ = "FAQ"


class ReviewStatus(str, Enum):
    """Moderation states for user-submitted reviews."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MenuItemStatus(str, Enum):
    """Availability states for vendor menu items."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
