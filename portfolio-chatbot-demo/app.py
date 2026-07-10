from fastapi import Header
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from diskcache import Cache
from litellm import completion
from hashlib import sha256
from datetime import datetime
import uvicorn
from dotenv import load_dotenv
import os

load_dotenv()

ADMIN_KEY = os.getenv("ADMIN_KEY")


app = FastAPI(title="Portfolio Chatbot API")

# ============================================================
# RESPONSE CACHE
# ============================================================

response_cache = Cache("./response_cache")


def get_cache_key(prompt: str):
    return sha256(prompt.strip().lower().encode()).hexdigest()


def get_cached_response(prompt: str):
    return response_cache.get(get_cache_key(prompt))


def save_response(prompt: str, answer: str):
    response_cache[get_cache_key(prompt)] = answer


def clear_response_cache():
    response_cache.clear()


# ============================================================
# RATE LIMITER
# ============================================================

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


def clear_rate_limit():
    rate_cache.clear()


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):
    prompt: str


# ============================================================
# CHAT ENDPOINT
# ============================================================

@app.post("/chat")
async def chat(data: ChatRequest, request: Request):

    prompt = data.prompt

    # Real client IP (works behind proxies too)
    ip = request.headers.get(
        "X-Forwarded-For",
        request.client.host
    ).split(",")[0].strip()

    # --------------------------------------------------------
    # CACHE FIRST
    # --------------------------------------------------------

    cached = get_cached_response(prompt)

    if cached:

        return {
            "cached": True,
            "remaining_questions": "Unlimited (Cache Hit)",
            "answer": cached
        }

    # --------------------------------------------------------
    # RATE LIMIT
    # --------------------------------------------------------

    allowed, remaining = allow_request(ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="You've reached today's limit of 10 new questions."
        )

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------

    try:

        response = completion(

            model="ollama/llama3.2:latest",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.2,

            fallbacks=[
                "gemini/gemini-2.5-flash",
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


# ============================================================
# RESET ENDPOINT
# ============================================================


@app.get("/reset")
def reset(x_admin_key: str = Header(...)):

    if x_admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin key."
        )

    clear_response_cache()
    clear_rate_limit()

    return {
        "message": "✅ Response cache and rate limit have been reset."
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def home():

    return {
        "status": "running",
        "message": "Portfolio Chatbot API"
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
