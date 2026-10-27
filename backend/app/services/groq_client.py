import json
import time
from collections.abc import Callable, Iterator

import httpx

from app.config import get_settings
from app.services.scoring_prompt import ScoreValidationError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_TOKENS = 400
MAX_RETRIES = 2
MAX_RETRY_AFTER_SECONDS = 60.0
DEFAULT_RETRY_AFTER_SECONDS = 20.0
TRANSIENT_SLEEP_SECONDS = 2.0
MOCK_CONTENT = json.dumps({"score": 55, "reason": "Mock score", "red_flags": []})


class GroqError(Exception):
    pass


class GroqRateLimited(GroqError):
    def __init__(self, wait_seconds: float):
        super().__init__("Groq rate limit reached")
        self.wait_seconds = wait_seconds


class GroqTransientError(GroqError):
    pass


class GroqAuthError(GroqError):
    pass


class GroqRequestError(GroqError):
    pass


def parse_retry_after(value: str | None) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER_SECONDS
    if seconds < 0:
        return DEFAULT_RETRY_AFTER_SECONDS
    return seconds


def extract_result(response: httpx.Response) -> tuple[str, int | None]:
    try:
        body = response.json()
        choice = body["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason")
        tokens = body.get("usage", {}).get("total_tokens")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ScoreValidationError("Unexpected response shape from Groq")
    if finish_reason == "length":
        raise ScoreValidationError("Groq response was cut off")
    if not isinstance(content, str):
        raise ScoreValidationError("Groq response has no text content")
    if isinstance(tokens, bool) or not isinstance(tokens, int):
        tokens = None
    return content, tokens


def call_groq(
    client: httpx.Client,
    messages: list[dict[str, str]],
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, int | None]:
    settings = get_settings()
    if settings.groq_api_key is not None:
        api_key = settings.groq_api_key.get_secret_value()
    elif settings.groq_mock:
        api_key = "mock"
    else:
        raise GroqAuthError("GROQ_API_KEY is not set")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
    }

    rate_retries = 0
    transient_retries = 0
    while True:
        try:
            response = client.post(GROQ_URL, json=payload, headers=headers)
        except httpx.HTTPError:
            if transient_retries >= MAX_RETRIES:
                raise GroqTransientError("Network error while calling Groq")
            transient_retries += 1
            sleep(TRANSIENT_SLEEP_SECONDS)
            continue

        status = response.status_code
        if status == 429:
            wait = parse_retry_after(response.headers.get("retry-after"))
            if wait > MAX_RETRY_AFTER_SECONDS or rate_retries >= MAX_RETRIES:
                raise GroqRateLimited(wait)
            rate_retries += 1
            sleep(wait)
            continue
        if status >= 500:
            if transient_retries >= MAX_RETRIES:
                raise GroqTransientError(f"Groq server error {status}")
            transient_retries += 1
            sleep(TRANSIENT_SLEEP_SECONDS)
            continue
        if status in (401, 403):
            raise GroqAuthError("Groq rejected the API key")
        if status != 200:
            raise GroqRequestError(f"Groq returned status {status}")
        return extract_result(response)


def mock_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": MOCK_CONTENT}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 100},
        },
    )


def get_groq_client() -> Iterator[httpx.Client]:
    if get_settings().groq_mock:
        client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    else:
        client = httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        yield client
    finally:
        client.close()