# Fastango

**Fastango** is a Django-inspired **modular application framework built on top of FastAPI**. It lets you build large, scalable FastAPI projects using **pluggable mini-apps**, similar to Django apps, with optional **DRM, access control, and security-first design**.

> ⚡ FastAPI speed · 🧩 Django-like apps · 🔐 Built-in security mindset

---

## 🚀 Why Fastango?

FastAPI is fast and modern, but as projects grow, managing routes, services, permissions, and business logic can become messy. Django solves this with its *app-based architecture* — Fastango brings that idea to **FastAPI**, without sacrificing performance or flexibility.

Fastango is designed for:

* Large FastAPI backends
* Multi-tenant systems
* DRM / protected APIs
* Research & production-ready systems
* Teams who love Django’s structure but need FastAPI’s speed

---

## ✨ Key Features

* 🧩 **Django-like Mini Apps**
  Each feature lives in its own self-contained app

* 🔌 **Pluggable Architecture**
  Enable/disable apps dynamically

* 🔐 **DRM & Access Control Ready**
  Built-in hooks for license checks, permissions, and policies

* ⚡ **FastAPI Native**
  Fully compatible with FastAPI dependencies, routers, and async

* 🏗️ **Clean Project Structure**
  Opinionated but flexible layout for long-term maintainability

* 🧪 **Test-Friendly**
  Easy unit and integration testing per app

---

## 📁 Project Structure

```text
Fastango_project/
│
├── app/
│   ├── core/                # Core framework logic
│   │   ├── registry.py      # App registry (like Django INSTALLED_APPS)
│   │   ├── permissions.py   # DRM & access control hooks
│   │   └── config.py
│   │
│   ├── apps/                # Mini apps live here
│   │   ├── users/
│   │   │   ├── routes.py
│   │   │   ├── models.py
│   │   │   ├── services.py
│   │   │   └── app.py       # App definition
│   │   │
│   │   ├── billing/
│   │   │   ├── routes.py
│   │   │   └── app.py
│   │
│   ├── main.py              # FastAPI entry point
│
├── tests/
├── pyproject.toml
└── README.md
```

---

## 🧩 What Is a Fastango App?

A **Fastango app** is a self-contained module that includes:

* Routes
* Business logic
* Models (ORM-agnostic)
* Permissions / DRM rules

Example `app.py`:

```python
from Fastango.core import AppConfig

class UsersApp(AppConfig):
    name = "users"
    version = "1.0.0"
    permissions = ["user.read", "user.write"]
```

---

## ⚙️ App Registration

Just like Django’s `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "app.apps.users",
    "app.apps.billing",
]
```

Fastango automatically:

* Loads routes
* Applies permissions
* Attaches middleware if needed

---

## 🔐 DRM & Security Model

Fastango is **security-first by design**.

Supported concepts:

* License validation
* Feature-based access control
* Role & permission checks
* Tenant-based isolation

You can plug in:

* JWT
* OAuth2
* API Keys
* Custom DRM logic

---

## 🧠 Design Philosophy

* **Structure over chaos**
* **Explicit over magic**
* **Security is not optional**
* **FastAPI remains the core**

Fastango does *not* replace FastAPI — it **organizes it**.

---

## 📦 Installation (Planned)

```bash
pip install Fastango
```

> 🚧 Currently under active development

---

## 🛣️ Roadmap

* [ ] App registry & lifecycle hooks
* [ ] Built-in permission system
* [ ] DRM / license enforcement layer
* [ ] CLI (`Fastango startapp`)
* [ ] Admin-style dashboard (optional)
* [ ] PyPI release

---

## 🤝 Contributing

Contributions are welcome!

* Fork the repo
* Create a feature branch
* Add tests
* Open a pull request

---

## 📜 License

MIT License

---

## ✍️ Author

**S M Dedar Alam**
Backend Software Engineer | Machine Learning & Security Researcher

---

> *Fastango — Bring Django’s structure to FastAPI, without slowing it down.*
