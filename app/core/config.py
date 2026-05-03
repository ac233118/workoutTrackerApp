import os


class Settings:
    MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://ac233118_db_user:17qflwYMttMouAAT@cluster0.wkkhjwa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DB_NAME   = os.getenv("DB_NAME", "Mistari")
    IS_ATLAS: bool = (
        "mongodb+srv://" in MONGO_URL
        or "mongodb.net"  in MONGO_URL
    )


    # ── Google OAuth ──────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "4845622529-v8feuu0c14si12kf7qjnr588gdsf0vue.apps.googleusercontent.com")

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET: str      = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM: str   = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_DAYS: int = int(os.getenv("JWT_EXPIRE_DAYS", "30"))


settings = Settings()
