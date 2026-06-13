#!/usr/bin/env python3
"""
TokenMix API - To'liq namuna skript
API: https://api.tokenmix.ai/v1
Model: gemini-2.5-flash
"""

from openai import OpenAI
import json

# ============================================================
# SOZLAMALAR
# ============================================================
TOKENMIX_API_KEY = "sk-tm-Avp3aN0fycfsTPM8KBn0JnoNoM7No5bK3bgep6Fd3kA0iazV"
TOKENMIX_BASE_URL = "https://api.tokenmix.ai/v1"

client = OpenAI(
    base_url=TOKENMIX_BASE_URL,
    api_key=TOKENMIX_API_KEY,
)

# ============================================================
# 1. BASIC CHAT COMPLETION
# ============================================================
def basic_chat():
    print("\n" + "="*60)
    print("1. BASIC CHAT COMPLETION")
    print("="*60)

    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Salom, o'zing haqingda qisqa ayt."},
        ],
        max_tokens=1024,
    )
    print("Javob:")
    print(response.choices[0].message.content)
    return response

# ============================================================
# 2. VISION - RASM TAHLILI
# ============================================================
def vision_analysis(image_url: str = None):
    print("\n" + "="*60)
    print("2. VISION - RASM TAHLILI")
    print("="*60)

    # Standart test rasmi (agar URL berilmasa)
    if not image_url:
        image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/300px-PNG_transparency_demonstration_1.png"

    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Bu rasmda nima bor? Tafsilotlarini ayt."},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        max_tokens=1024,
    )
    print("Javob:")
    print(response.choices[0].message.content)
    return response

# ============================================================
# 3. FUNCTION CALLING
# ============================================================
def function_calling():
    print("\n" + "="*60)
    print("3. FUNCTION CALLING")
    print("="*60)

    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Toshkentda havo harorati qanday?"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "City name"},
                            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                        },
                        "required": ["location"],
                    },
                },
            }
        ],
    )

    message = response.choices[0].message

    if message.tool_calls:
        print("Funksiya chaqiruvi aniqlandi:")
        for tool_call in message.tool_calls:
            print(f"  Funksiya: {tool_call.function.name}")
            print(f"  Argumentlar: {tool_call.function.arguments}")

            # JSON parse qilish
            args = json.loads(tool_call.function.arguments)
            print(f"  Parsed: {args}")
    else:
        print("Javob:")
        print(message.content)

    return response

# ============================================================
# 4. STREAMING
# ============================================================
def streaming_chat():
    print("\n" + "="*60)
    print("4. STREAMING")
    print("="*60)

    stream = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[{"role": "user", "content": "Qisqa she'r yoz."}],
        stream=True,
    )

    print("Javob (stream):")
    full_response = ""
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)
            full_response += content
    print()  # Yangi qator
    return full_response

# ============================================================
# 5. MODELNI TEKSHIRISH (bir nechta modellar)
# ============================================================
def test_models():
    print("\n" + "="*60)
    print("5. MODEL TEKSHIRUVI")
    print("="*60)

    models = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash",
        "gemini-3.5-flash",
    ]

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Salom"}],
                max_tokens=10,
            )
            print(f"✅ {model}: OK - {response.choices[0].message.content[:30]}...")
        except Exception as e:
            print(f"❌ {model}: {type(e).__name__} - {str(e)[:60]}")

# ============================================================
# ASOSIY ISHGA TUSHIRISH
# ============================================================
if __name__ == "__main__":
    print("TokenMix API Test")
    print(f"URL: {TOKENMIX_BASE_URL}")
    print(f"API Key: {TOKENMIX_API_KEY[:15]}...")

    try:
        # 1. Basic chat
        basic_chat()

        # 2. Vision (ixtiyoriy - rasm URL kerak)
        # vision_analysis("https://your-image-url.jpg")

        # 3. Function calling
        function_calling()

        # 4. Streaming
        streaming_chat()

        # 5. Model test
        test_models()

    except Exception as e:
        print(f"\n❌ Xatolik: {type(e).__name__}: {e}")
