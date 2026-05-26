# Fastango Architecture Blueprint: Bringing Django's Modular Structure to FastAPI

> **Fastango** — *Bring Django’s structure to FastAPI, without slowing it down.*
>
> Fastango is a Django-inspired modular project boilerplate built on top of FastAPI. It allows you to build large, scalable FastAPI projects using pluggable mini-apps (similar to Django apps) with optional DRM (Digital Rights Management / permissions), access control, and a security-first design.

This document serves as the foundational spec and production-ready blueprint for **Fastango**. It derives structural rules from a large Django/DRF project (`core-backend`) and translates them into pluggable, highly performant FastAPI mini-apps.

---

## 1. Current Architecture Overview (Django/DRF)

The existing project is built on **Django** and **Django REST Framework (DRF)**, utilizing a modular, domain-driven architecture with clean separation of layers.

### Main Directory Layout
```text
core-backend/
├── config/                  # Global application settings, celery, routing configuration
│   ├── settings/            # Environment-specific settings files
│   ├── urls.py              # Root URL router combining versioned public/private patterns
│   └── celery.py            # Celery background tasks config
├── core/
│   ├── apps/                # Domain modules grouping logically related sub-domains
│   │   ├── admin/           # Admin-related services (auth, home, profile)
│   │   ├── customer/        # Customer-facing services (auth, home, profile)
│   │   ├── vendor/          # Vendor-specific domain (auth, home, menu, profile)
│   │   ├── platform/        # Platform utilities (order, payment, payout, notification, content, review)
│   │   ├── common/          # Shared utilities, global models, and custom decorators
│   │   └── urls.py          # Unified domain API router
│   ├── middleware.py        # Custom Django request/response middlewares
│   ├── utils/               # Shared helper functions
│   └── templates/           # Static templates if required
├── requirements/            # Split pip dependencies (base, local, production)
├── manage.py                # Django CLI tool
└── pytest.ini / setup.cfg   # Testing & linting configurations
```

### Logical Layering of a Single Module
Every sub-domain leaf (e.g., `core/apps/customer/profile`) is organized into the following strict, decoupled layers:

1. **Database Layer (`models.py`)**: Defines ORM schemas extending a shared `CommonFieldModel` (which provides `created_at`, `updated_at`, and `is_active`).
2. **Repository/Query Layer (`queries.py`)**: Encapsulates DB retrieval operations. Reads do not happen directly in the services; instead, they are abstracted into clean query functions that can easily hook into caching mechanisms (e.g., `@cache_query()`).
3. **Data Validation Layer (`validators.py`)**: Uses **Pydantic v2** models to validate incoming HTTP request payloads.
4. **Service Layer (`api/v1/services.py`)**: Implements application-specific business use-cases, transactional boundaries (`@transaction.atomic`), external S3/Cloud Storage actions, and schema dict mappings.
5. **Controller Layer (`api/v1/views.py`)**: Binds HTTP methods (`GET`, `POST`, `PATCH`, etc.) using DRF `APIView`. It utilizes two core decorators:
   - `@api_response()`: Standardizes the response envelope format, handles exceptions globally, and logs interactions to an `AuditLog` table.
   - `@validate(Schema)`: Extracts incoming payload data, runs it through a Pydantic schema, and attaches the validated data model to the request object (`request.validated_data`).
6. **Routing Layer (`api/v1/urls.py` & `core/apps/urls.py`)**: Structures routes systematically, splitting public/private paths and grouping them dynamically under a version prefix (e.g., `/api/v1/customer/profile`).

---

## 2. FastAPI Architecture Translation Map

When porting this architecture to **FastAPI**, we gain a massive boost in performance (via native asynchronous execution) and cleaner code since FastAPI is **Pydantic-first** natively.

Here is how the Django concepts map to FastAPI components:

| Django/DRF Component | FastAPI Equivalent | Implementation Approach |
| :--- | :--- | :--- |
| **Django ORM Models (`models.py`)** | **SQLAlchemy / SQLModel** | Use asynchronous SQLAlchemy with ORM models or SQLModel for unified models and Pydantic schemas. |
| **`queries.py` (Query Layer)** | **Asynchronous Repositories** | Define async python functions that receive a SQLAlchemy `AsyncSession` and fetch database records. |
| **`validators.py` (Pydantic)** | **Native FastAPI Pydantic Schemas** | Declare standard Pydantic models. FastAPI handles validation and generates Swagger schema automatically. |
| **`views.py` (Views Layer)** | **APIRouter Endpoints** | Use `APIRouter` with decorated async path functions (`@router.get`, `@router.post`). |
| **`@validate` Decorator** | **FastAPI Native Dependency** | Replaced entirely. Pass the Pydantic schema as a parameter to the endpoint, and FastAPI automatically performs validation. |
| **`@api_response` Decorator** | **Global Exception Handler & Response Model** | Use FastAPI `exception_handlers` for uniform errors and a base `ResponseModel` for standard response envelopes. |
| **`urls.py` (Nested Routing)** | **Nested `APIRouter.include_router()`** | Standard router chains that inherit versioning prefixes (`/api/v1`) and security tags. |
| **`AuditLog` and Decorators** | **FastAPI Middleware / Dependencies** | Use an `APIRoute` subclass or a Router dependency to audit requests, responses, and log to DB asynchronously. |
| **Django Sessions/Authentication** | **FastAPI Dependencies (`Depends`)** | Decouple authentication by injecting a JWT decoder or session resolver via FastAPI’s Dependency Injection system. |

---

## 3. Proposed FastAPI Project Template Structure

Below is the directory template designed to replicate the modular, domain-driven structure of your Django app in FastAPI.

```text
fastapi-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI Application Factory, global middlewares & exception handlers
│   ├── config.py                # Centralized settings loading env variables via Pydantic BaseSettings
│   ├── database.py              # Async SQLAlchemy engine, session maker, and DB dependency helper
│   ├── core/                    # Shared infrastructure, decorators, security utilities
│   │   ├── __init__.py
│   │   ├── security.py          # Password hashing, JWT creation & verification
│   │   ├── storage.py           # AWS S3 Cloud Storage service layer
│   │   ├── audit.py             # Asynchronous audit log handler (DB logger)
│   │   ├── exceptions.py        # Custom application exceptions and error mappings
│   │   └── responses.py         # Standard API Response Envelope schema and helper functions
│   └── modules/                 # Modular Domain Directories (corresponds to core/apps/)
│       ├── __init__.py
│       ├── common/              # Shared models, enums and schemas across domains
│       │   ├── __init__.py
│       │   ├── models.py        # Base async models (TimeStampedBase, CommonFieldBase)
│       │   └── enums.py         # Shared enums (e.g. RoleType, GenderType)
│       │
│       ├── admin/               # Admin domain logic
│       │   ├── __init__.py
│       │   ├── auth/
│       │   ├── home/
│       │   └── profile/
│       │
│       ├── customer/            # Customer domain logic
│       │   ├── __init__.py
│       │   ├── auth/
│       │   ├── home/
│       │   └── profile/         # Leaf-level Customer Profile module
│       │       ├── __init__.py
│       │       ├── models.py    # Database models (SQLAlchemy)
│       │       ├── constants.py # Constants and module-specific enums
│       │       ├── schemas.py   # Pydantic schemas (replacing validators.py)
│       │       ├── repositories.py # Database query operations (replacing queries.py)
│       │       ├── services.py  # Business logic/use-case layer
│       │       └── router.py    # APIRouter paths (replacing views.py & urls.py)
│       │
│       ├── vendor/              # Vendor domain logic
│       │   ├── __init__.py
│       │   ├── auth/
│       │   ├── home/
│       │   ├── menu/
│       │   └── profile/
│       │
│       └── platform/            # Platform generic modules
│           ├── __init__.py
│           ├── order/
│           ├── payment/
│           ├── payout/
│           ├── notification/
│           ├── content/
│           └── review/
│
├── tests/                       # Complete pytest suite mirroring the application structure
│   ├── __init__.py
│   ├── conftest.py
│   └── modules/
├── pyproject.toml               # Poetry/PIP package settings and metadata
├── docker-compose.yml           # Local multi-container orchestration (FastAPI, Postgres, Redis)
└── local.env                    # Local environment secrets configurations
```

---

## 4. FastAPI Component Code Blueprints

Here is the exact code architecture showing how to implement this clean, robust FastAPI template.

### 4.1. Core Database Configuration (`app/database.py`)
Sets up an asynchronous engine and session manager using standard SQLAlchemy 2.0.

```python
# app/database.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings

# Create asynchronous engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=10,
    max_overflow=20
)

# Create session generator
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# FastAPI Dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### 4.2. Core Response Envelope (`app/core/responses.py`)
Standardizes all successful API responses into a unified structure, matching the behavior of your original Django `@api_response` decorator.

```python
# app/core/responses.py
from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    error: bool = False
    message: str = "Request executed successfully"
    data: Optional[T] = None

def success_response(data: Any = None, message: str = "Request executed successfully") -> dict:
    """Helper to return standardized dictionary formats"""
    return {
        "error": False,
        "message": message,
        "data": data
    }
```

### 4.3. Abstract Models (`app/modules/common/models.py`)
Creates the abstract database models to replicate Django's abstract base model inheritance.

```python
# app/modules/common/models.py
from datetime import datetime
from sqlalchemy import DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class TimeStampedBase(Base):
    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now()
    )

class CommonFieldBase(TimeStampedBase):
    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
```

### 4.4. Domain DB Schema Model (`app/modules/customer/profile/models.py`)
Maps the Django customer profile model structure cleanly into a modern SQLAlchemy class.

```python
# app/modules/customer/profile/models.py
import uuid
from sqlalchemy import String, Date, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.modules.common.models import CommonFieldBase

class CustomerProfile(CommonFieldBase):
    __tablename__ = "customer_profile"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_code: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False, server_default="OTHERS")
    estimated_dob: Mapped[Date] = mapped_column(Date, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
```

### 4.5. Domain Schemas (`app/modules/customer/profile/schemas.py`)
Defines incoming request payloads using native Pydantic validation.

```python
# app/modules/customer/profile/schemas.py
from typing import Optional
from pydantic import BaseModel, Field

class CustomerProfileCreateSchema(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=20)
    gender: str = Field("OTHERS", max_length=20)
    age: int = Field(..., ge=0, le=150)
    address: str

class CustomerProfileUpdateSchema(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    gender: Optional[str] = Field(None, max_length=20)
    age: Optional[int] = Field(None, ge=0, le=150)
    address: Optional[str] = None

class CustomerProfileOutSchema(BaseModel):
    first_name: str
    last_name: str
    phone: str
    gender: str
    age: int
    address: str

    class Config:
        from_attributes = True
```

### 4.6. Repository / Query Layer (`app/modules/customer/profile/repositories.py`)
Instead of running database logic directly inside services, database lookups are kept separate to ensure clean query layers, allowing for caching decorators to be applied later if needed.

```python
# app/modules/customer/profile/repositories.py
import uuid
from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.customer.profile.models import CustomerProfile

class CustomerProfileRepository:
    @staticmethod
    async def get_by_customer_code(db: AsyncSession, customer_code: uuid.UUID) -> Optional[CustomerProfile]:
        query = select(CustomerProfile).where(
            CustomerProfile.customer_code == customer_code,
            CustomerProfile.is_active == True
        )
        result = await db.execute(query)
        return result.scalars().first()

    @staticmethod
    async def get_all_active(db: AsyncSession) -> Sequence[CustomerProfile]:
        query = select(CustomerProfile).where(CustomerProfile.is_active == True)
        result = await db.execute(query)
        return result.scalars().all()
```

### 4.7. Service Layer (`app/modules/customer/profile/services.py`)
Orchestrates business logic and service dependencies. Notice that transaction logic is cleanly managed using SQLAlchemy `async with db.begin():` blocks.

```python
# app/modules/customer/profile/services.py
import uuid
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.customer.profile.repositories import CustomerProfileRepository
from app.modules.customer.profile.models import CustomerProfile
from app.modules.customer.profile.schemas import CustomerProfileCreateSchema, CustomerProfileUpdateSchema
from app.modules.customer.profile.constants import (
    PROFILE_CREATED_MSG, PROFILE_EXISTS_MSG, PROFILE_NOT_FOUND_MSG, PROFILE_UPDATED_MSG
)

# Dummy utility service mapping age to date of birth
class AgeDateService:
    @staticmethod
    def age_to_estimated_dob(age: int):
        from datetime import date
        return date(date.today().year - age, 1, 1)

    @staticmethod
    def estimated_dob_to_age(dob) -> int:
        from datetime import date
        return date.today().year - dob.year

class CustomerProfileService:
    def __init__(self, db: AsyncSession, customer_code: uuid.UUID):
        self.db = db
        self.customer_code = customer_code

    async def get_profile(self) -> Tuple[Optional[dict], Optional[str]]:
        profile = await CustomerProfileRepository.get_by_customer_code(self.db, self.customer_code)
        if not profile:
            return None, PROFILE_NOT_FOUND_MSG
        return self._to_dict(profile), None

    async def create_profile(self, data: CustomerProfileCreateSchema) -> Tuple[Optional[dict], str]:
        # Wrap execution in an active atomic transaction block
        async with self.db.begin():
            existing = await CustomerProfileRepository.get_by_customer_code(self.db, self.customer_code)
            if existing:
                return None, PROFILE_EXISTS_MSG

            estimated_dob = AgeDateService.age_to_estimated_dob(data.age)
            profile = CustomerProfile(
                customer_code=self.customer_code,
                first_name=data.first_name,
                last_name=data.last_name,
                phone=data.phone,
                gender=data.gender,
                estimated_dob=estimated_dob,
                address=data.address
            )
            self.db.add(profile)
            await self.db.flush() # Flush to populate ID but keep transaction active

        await self.db.refresh(profile) # Fetch fresh from DB after commit hook
        return self._to_dict(profile), PROFILE_CREATED_MSG

    async def update_profile(self, data: CustomerProfileUpdateSchema) -> Tuple[Optional[dict], Optional[str]]:
        async with self.db.begin():
            profile = await CustomerProfileRepository.get_by_customer_code(self.db, self.customer_code)
            if not profile:
                return None, PROFILE_NOT_FOUND_MSG

            update_data = data.model_dump(exclude_unset=True)
            if "age" in update_data:
                profile.estimated_dob = AgeDateService.age_to_estimated_dob(update_data.pop("age"))

            for key, val in update_data.items():
                setattr(profile, key, val)

        await self.db.refresh(profile)
        return self._to_dict(profile), PROFILE_UPDATED_MSG

    def _to_dict(self, profile: CustomerProfile) -> dict:
        return {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "phone": profile.phone,
            "gender": profile.gender,
            "age": AgeDateService.estimated_dob_to_age(profile.estimated_dob),
            "address": profile.address
        }
```

### 4.8. Routing / Controller Layer (`app/modules/customer/profile/router.py`)
FastAPI routers replace the Django views layer. Notice the integration of dependencies for DB session injection (`get_db`) and security context retrieval (`get_current_user_code`).

```python
# app/modules/customer/profile/router.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.responses import APIResponse, success_response
from app.modules.customer.profile.schemas import CustomerProfileCreateSchema, CustomerProfileUpdateSchema, CustomerProfileOutSchema
from app.modules.customer.profile.services import CustomerProfileService

router = APIRouter(prefix="/profile", tags=["Customer Profile"])

# Mock Authentication Dependency to get customer session metadata
async def get_current_user_code() -> uuid.UUID:
    # In production, extract user claims from request authorization header JWT
    return uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")

@router.get("", response_model=APIResponse[CustomerProfileOutSchema])
async def get_profile(
    db: AsyncSession = Depends(get_db),
    customer_code: uuid.UUID = Depends(get_current_user_code)
):
    service = CustomerProfileService(db, customer_code)
    data, error_msg = await service.get_profile()
    if error_msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    return success_response(data=data)

@router.post("", response_model=APIResponse[CustomerProfileOutSchema])
async def create_profile(
    payload: CustomerProfileCreateSchema,
    db: AsyncSession = Depends(get_db),
    customer_code: uuid.UUID = Depends(get_current_user_code)
):
    service = CustomerProfileService(db, customer_code)
    data, msg = await service.create_profile(payload)
    if data is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return success_response(data=data, message=msg)

@router.patch("", response_model=APIResponse[CustomerProfileOutSchema])
async def update_profile(
    payload: CustomerProfileUpdateSchema,
    db: AsyncSession = Depends(get_db),
    customer_code: uuid.UUID = Depends(get_current_user_code)
):
    service = CustomerProfileService(db, customer_code)
    data, error_msg = await service.update_profile(payload)
    if error_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    return success_response(data=data, message="Profile updated successfully")
```

### 4.9. Main Aggregator (`app/main.py`)
This file is the root application config, mounting versioned routes and applying middleware & central exception handlers.

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONModelResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time

from app.core.responses import success_response
from app.modules.customer.profile.router import router as customer_profile_router
from app.core.audit import AuditLogService  # Hypothetical audit logging service

app = FastAPI(
    title="Core Asynchronous Backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Request/Response Interceptor for Request ID and Logging (Replaces middlewares)
@app.middleware("http")
async def audit_and_time_middleware(request: Request, call_next):
    start_time = time.time()

    # Process request
    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    # Extract endpoint, payload metadata and execute async Audit logging hook
    # await AuditLogService.log_request(request, response, process_time)

    return response

# Standardize global generic exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": f"Internal server error: {str(exc)}",
            "data": None
        }
    )

# Version 1 Router Aggregation (Replicates core/apps/urls.py patterns)
v1_customer_router = APIRouter(prefix="/api/v1/customer")
v1_customer_router.include_router(customer_profile_router)

# Mount Routers
app.include_router(v1_customer_router)
```

---

## 5. Benefits of this Modular FastAPI Template

1. **Ultra Fast Async Processing**: Natively supports `async`/`await` for blazing fast database I/O and S3 operations compared to synchronous WSGI Django setups.
2. **True Layered Isolation**:
   - `repositories.py` abstracts ORM models away from services.
   - `services.py` holds pure business use-cases, unaware of request/response headers or formats.
   - `router.py` parses endpoints, handles dependencies, and responds in a unified format.
3. **Pydantic-First**: Direct type validation, request parameters parsing, response mapping, and self-documenting JSON schemas generated out of the box in the visual Swagger dashboard.
4. **Scale-Ready Folder Layout**: Grouping logical scopes (`customer`, `vendor`, `admin`, `platform`) separately prevents spaghetti code and circular imports, making a transition painless for developers familiar with modular Django structures.

---
