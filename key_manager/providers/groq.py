from .base import ProviderBase


class GroqProvider(ProviderBase):
    name = "groq"
    base_url = "https://api.groq.com"
    check_endpoint = "/openai/v1/models"
