import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
import datetime

# --- Configuration ---
PROJECT_ID = "vdc200015-ai-cxm-2-np"
LOCATION = "us-central1"

# --- Models to Test ---
# A selection of common image and video models.
# This list can be expanded with other models you want to test.
IMAGE_MODELS = [
    "imagegeneration@006",
    "imagegeneration@005",
    "imagegeneration@002",
    "imagen@001", # Older model, might not be available
]

# VIDEO_MODELS = [
#     "videogeneration@001"
#     # Add other video model names here as they become available
# ]

def test_image_models(project_id, location):
    """Iterates through and tests a list of image generation models."""
    print("\n--- Testing Image Generation Models ---")
    for model_name in IMAGE_MODELS:
        print(f"\n--- Testing model: {model_name} ---")
        try:
            # 1. Initialize the model
            print("Step 1: Initializing model...")
            model = ImageGenerationModel.from_pretrained(model_name)
            print("...Initialization successful.")

            # 2. Generate an image
            prompt = f"A futuristic cityscape at sunset, cinematic lighting, high detail. Model: {model_name}"
            print(f"Step 2: Sending prompt: \"{prompt[:50]}...\"")
            response = model.generate_images(
                prompt=prompt,
                number_of_images=1,
                # You can add other parameters here, e.g., aspect_ratio="16:9"
            )
            print("...Image generation successful.")

            # 3. Save the image
            print("Step 3: Saving image...")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_image_{model_name.replace('@', '_')}_{timestamp}.png"
            response.images[0].save(filename)
            print(f"...SUCCESS! Image saved to '{filename}'")

        except Exception as e:
            print(f"...TEST FAILED for model '{model_name}'.")
            print("   Error:")
            print(f"   {e}")
            print("-" * 20)

# def test_video_models(project_id, location):
#     """Iterates through and tests a list of video generation models."""
#     print("\n--- Testing Video Generation Models ---")
#     # This section is commented out to resolve the ImportError.
#     # We will re-address video generation after confirming image generation works.
#     pass


if __name__ == "__main__":
    print("--- Vertex AI Image and Video Model Test ---")
    print(f"Project ID: {PROJECT_ID}")
    print(f"Location:   {LOCATION}")
    print("\nNOTE: This script uses Application Default Credentials (ADC).")
    print("Ensure you have run 'gcloud auth application-default login' in your terminal.")

    try:
        print("\nInitializing Vertex AI...")
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        print("...Initialization successful.")

        # Run the tests
        test_image_models(PROJECT_ID, LOCATION)
        # test_video_models(PROJECT_ID, LOCATION) # Commented out for now

        print("\n--- All Tests Completed ---")

    except Exception as e:
        print("\n--- SCRIPT FAILED TO INITIALIZE ---")
        print("An error occurred during Vertex AI initialization.")
        print("\n**Error Details:**")
        print(e)
