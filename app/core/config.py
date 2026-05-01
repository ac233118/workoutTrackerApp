import os


class Settings:
    MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://ac233118_db_user:17qflwYMttMouAAT@cluster0.wkkhjwa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DB_NAME   = os.getenv("DB_NAME", "Mistari")
    IS_ATLAS: bool = (
        "mongodb+srv://" in MONGO_URL
        or "mongodb.net"  in MONGO_URL
    )


settings = Settings()
