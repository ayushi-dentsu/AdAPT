import os
import requests
import json

# --- Configuration ---
# Make sure you have set the VERTEX_API_KEY environment variable in your terminal
# For PowerShell: $env:VERTEX_API_KEY="YOUR_API_KEY"
API_KEY = os.getenv("VERTEX_API_KEY")
PROJECT_ID = "vdc200015-ai-cxm-2-np"
LOCATION = "us-central1"
MODEL_ID = "imagen-4.0-generate-001" # The new model ID to test

# The Vertex AI API endpoint for image generation
# Note: The exact endpoint can vary. This is a common structure.
ENDPOINT_URL = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{MODEL_ID}:predict"

def test_direct_api_call():
    """
    Tests the Vertex AI API with a direct HTTP request using an API key.
    """
    print("--- Direct Vertex AI API Call Test ---")

    if not API_KEY:
        print("\n--- TEST FAILED ---")
        print("Error: The 'VERTEX_API_KEY' environment variable is not set.")
        print("Please set it in your terminal before running the script.")
        return

    print(f"Project ID: {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print(f"Model ID:   {MODEL_ID}")
    print("API Key found in environment variables.")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # A simple payload for the image generation model
    payload = {
        "instances": [
            {
                "prompt": "A photo of a majestic lion in the savanna at sunrise, high detail"
            }
        ],
        "parameters": {
            "sampleCount": 1
        }
    }

    print("\nSending request to the Vertex AI endpoint...")
    try:
        response = requests.post(ENDPOINT_URL, headers=headers, data=json.dumps(payload))

        # Check the response
        print(f"\nReceived response with status code: {response.status_code}")

        if response.status_code == 200:
            print("\n--- SUCCESS! ---")
            print("The API call was successful. The API key has the necessary permissions.")
            # You can print the full response to inspect the output
            # print("\nResponse JSON:")
            # print(response.json())
        else:
            print("\n--- TEST FAILED ---")
            print("The API call failed. Details below:")
            print("\nResponse Content:")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print("\n--- TEST FAILED ---")
        print("An error occurred while making the HTTP request.")
        print("\n**Error Details:**")
        print(e)

if __name__ == "__main__":
    test_direct_api_call()
