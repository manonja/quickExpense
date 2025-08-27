from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    qb_base_url: str
    qb_client_id: str
    qb_client_secret: str
    qb_redirect_uri: str
    qb_company_id: str
    qb_access_token: str
    qb_refresh_token: str

    class Config:
        env_file = ".env"


settings = Settings()
