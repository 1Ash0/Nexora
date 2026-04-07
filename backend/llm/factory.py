from backend.config.settings import settings


def create_chat_model(*, temperature: float = 0.0):
    """Create a chat model from configured provider settings."""
    provider = (settings.LLM_PROVIDER or "groq").strip().lower()

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            temperature=temperature,
            max_retries=6,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=temperature,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")
