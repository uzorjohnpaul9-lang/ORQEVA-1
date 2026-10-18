import os
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Settings(BaseSettings):
    APP_NAME: str = "ORQEVA"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Supabase is the database + auth provider. Keys from the dashboard:
    #   Settings -> API Keys. Use the NEW publishable + secret keys.
    #   publishable (sb_publishable_...) -> SUPABASE_PUBLISHABLE_KEY (low-priv, anon+RLS)
    #   secret      (sb_secret_...)      -> SUPABASE_SECRET_KEY      (server-only, BYPASSRLS)
    # Legacy JWT-based keys kept as fallbacks so projects that haven't migrated yet
    # (anon/service_role) keep working. See https://supabase.com/docs/guides/getting-started/api-keys
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv(
        "SUPABASE_PUBLISHABLE_KEY", os.getenv("SUPABASE_ANON_KEY", "")
    )
    SUPABASE_SECRET_KEY: str = os.getenv(
        "SUPABASE_SECRET_KEY", os.getenv("SUPABASE_SERVICE_KEY", "")
    )
    # Only used for Legacy HS256 local token verification. NOT required.
    # Modern verification is server-side via client.auth.get_user(token) / JWKS.
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    CORS_ORIGINS: list[str] | None = None
    # Regex for origins that can't be enumerated ahead of time - Cloudflare Pages
    # serves every deployment and preview at its own <hash>.orqeva.pages.dev URL.
    # Only the canonical origin is pinned in CORS_ORIGINS; this covers the rest.
    CORS_ORIGIN_REGEX: str | None = os.getenv(
        "CORS_ORIGIN_REGEX", r"https://[a-z0-9-]+\.orqeva\.pages\.dev"
    )

    @model_validator(mode="before")
    @classmethod
    def _parse_cors(cls, values):
        """Accept a JSON array or the conventional comma-separated list.

        Comma-separated is what most operators reach for first; rejecting it made
        a fresh deploy fail at startup with a pydantic validation error.
        """
        origins = values.get("CORS_ORIGINS")
        if isinstance(origins, str):
            raw = origins.strip()
            if raw.startswith("["):
                import json

                try:
                    values["CORS_ORIGINS"] = json.loads(raw)
                except json.JSONDecodeError:
                    values["CORS_ORIGINS"] = [
                        o.strip() for o in raw.strip("[]").split(",") if o.strip()
                    ]
            else:
                values["CORS_ORIGINS"] = [o.strip() for o in raw.split(",") if o.strip()]
        return values

    # Email (any SMTP provider: Gmail app-password, Resend SMTP, Brevo...)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "ORQEVA <no-reply@orqeva.com>"
    APP_BASE_URL: str = "http://localhost:3000"
    # Where support tickets are announced (optional). Empty = no email notify.
    SUPPORT_EMAIL: str = os.getenv("SUPPORT_EMAIL", "")

    # Error tracking (optional). Empty = Sentry disabled.
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

    @model_validator(mode="after")
    def _validate_supabase(self):
        missing = [
            name
            for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY")
            if not getattr(self, name)
        ]
        if missing:
            import warnings

            warnings.warn(
                "Supabase not configured - set SUPABASE_URL, SUPABASE_SERVICE_KEY and "
                f"SUPABASE_ANON_KEY in .env (missing: {', '.join(missing)}). "
                "All database/auth calls will fail until this is done.",
                stacklevel=1,
            )
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()