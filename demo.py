from fastapi import FastAPI, Request, HTTPException
from diskcache import Cache
from litellm import completion
from hashlib import sha256
from datetime import datetime
import uvicorn

app = FastAPI(title="Portfolio Chatbot Demo")

# ==========================
# Response Cache
# ==========================

response_cache = Cache("./response_cache")


def get_cache_key(prompt: str):
    return sha256(prompt.strip().lower().encode()).hexdigest()


def get_cached_response(prompt: str):
    key = get_cache_key(prompt)
    return response_cache.get(key)


def save_response(prompt: str, response: str):
    key = get_cache_key(prompt)
    response_cache[key] = response


# ==========================
# Rate Limiter
# ==========================

rate_cache = Cache("./rate_limit")

LIMIT = 10


def allow_request(ip: str):

    today = datetime.now().strftime("%Y-%m-%d")

    key = f"{ip}:{today}"

    count = rate_cache.get(key, default=0)

    if count >= LIMIT:
        return False, 0

    rate_cache[key] = count + 1

    return True, LIMIT - (count + 1)


# ==========================
# Chat Endpoint
# ==========================

@app.get("/chat")
async def chat(prompt: str, request: Request):

    # Get real IP if behind proxy
    ip = request.headers.get(
        "X-Forwarded-For",
        request.client.host
    ).split(",")[0].strip()

    # ------------------------
    # Rate Limit
    # ------------------------

    allowed, remaining = allow_request(ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="You've reached today's limit of 10 questions."
        )

    # ------------------------
    # Cache
    # ------------------------

    cached = get_cached_response(prompt)

    if cached:
        return {
            "cached": True,
            "remaining_questions": remaining,
            "answer": cached
        }

    # ------------------------
    # LiteLLM
    # ------------------------

    try:

        response = completion(

            model="groq/openai/gpt-oss-120b",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.3,

            fallbacks=[
                "ollama/llama3.2:latest",
            ],

            num_retries=3,

            timeout=20

        )

        answer = response.choices[0].message.content

        save_response(prompt, answer)

        return {
            "cached": False,
            "remaining_questions": remaining,
            "answer": answer
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ==========================
# Run
# ==========================

if __name__ == "__main__":

    uvicorn.run(
        "demo:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
