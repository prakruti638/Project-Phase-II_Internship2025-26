import os
import base64
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def test_groq_vision():
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_llama")
    if not api_key:
        print("❌ No Groq API Key found in .env")
        return

    print(f"Testing Groq Vision with key starting with: {api_key[:10]}...")
    client = Groq(api_key=api_key)
    
    # Create a tiny 1x1 black pixel as a test image
    pixel_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    base64_image = base64.b64encode(pixel_data).decode('utf-8')

    try:
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-instant",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=20,
        )
        print(f"✅ Groq Vision Response: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Groq Vision Error: {e}")

if __name__ == "__main__":
    test_groq_vision()
