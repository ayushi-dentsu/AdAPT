import vertexai
from vertexai.preview.generative_models import GenerativeModel

# --- Configuration ---
# This should be the same project ID as in your app.py
PROJECT_ID = "vdc200015-ai-cxm-2-np"
LOCATION = "us-central1"

print("--- Minimal Vertex AI ADC Test ---")
print(f"Project ID: {PROJECT_ID}")
print(f"Location:   {LOCATION}")
print("\nNOTE: This script uses Application Default Credentials (ADC).")
print("Ensure you have run 'gcloud auth application-default login' in your terminal.")

try:
    # 1. Initialize Vertex AI
    print("\nStep 1: Initializing Vertex AI...")
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print("...Initialization successful.")

    # 2. Select a Model
    print("\nStep 2: Selecting the 'gemini-2.5-pro' model...")
    model = GenerativeModel("gemini-2.5-pro")
    print("...Model selection successful.")

    # 3. Run a Hello World Prompt
    print("\nStep 3: Sending a 'Hello, world' prompt...")
    response = model.generate_content("Hello, world")
    print("...Prompt sent successfully.")

    # 4. Print the Response
    print("\n--- SUCCESS! ---")
    print("Received response from Vertex AI:")
    print(response.text)

except Exception as e:
    print("\n--- TEST FAILED ---")
    print("An error occurred during the test.")
    print("\n**Error Details:**")
    print(e)
