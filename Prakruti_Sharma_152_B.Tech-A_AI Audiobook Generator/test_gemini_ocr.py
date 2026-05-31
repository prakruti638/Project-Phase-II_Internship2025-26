import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def test_gemini_vision():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ No Gemini API Key found in .env")
        return

    print(f"Testing Gemini Vision with key starting with: {api_key[:10]}...")
    client = genai.Client(api_key=api_key)
    
    # Create a tiny 1x1 black pixel as a test image
    import base64
    pixel_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                "Extract text from this image.",
                types.Part.from_bytes(data=pixel_data, mime_type="image/png")
            ]
        )
        print(f"SUCCESS: Gemini Vision Response: {response.text}")
    except Exception as e:
        print(f"ERROR: Gemini Vision Error: {str(e)}")

if __name__ == "__main__":
    test_gemini_vision()
