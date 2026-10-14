"""Settings, all from the environment.

There is no config file. Every deployment difference - which database, which
model, which admin password - is an environment variable, so the same image
runs in dev, test and prod.
"""
import base64

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QM_", env_file=".env", extra="ignore")

    # database
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "questionme_dev"
    db_password: str = ""
    db_name: str = "questionme_dev"

    # admin login - one account, no signup, no reset
    admin_user: str = "brian"
    # An argon2 hash is full of "$" and Docker Compose interpolates "$" in
    # env_file, which silently eats $argon2id, $v and $m and leaves a stump
    # that can never verify. So the deployed form is base64 and the plain
    # field stays for local use.
    admin_password_hash: str = ""          # argon2 hash; see `python -m app.hashpw`
    admin_password_hash_b64: str = ""      # same hash, base64 - safe through compose
    session_secret: str = ""           # signs the admin session cookie

    # the link candidates are sent; used to build invitation URLs
    public_base_url: str = "http://localhost:4200"

    # Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    environment: str = "dev"

    @property
    def admin_hash(self) -> str:
        if self.admin_password_hash_b64:
            return base64.b64decode(self.admin_password_hash_b64).decode()
        return self.admin_password_hash

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()
