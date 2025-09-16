#!/usr/bin/env python3
"""
Brand Style Analysis Component - Cloud Function
Analyze brand style from images/logos using Gemini multimodal.
"""

import functions_framework
import json
import tempfile
import os
from google.cloud import storage
from google.cloud import aiplatform
from vertexai.preview.generative_models import GenerativeModel
from vertexai.preview.generative_models import Image as VertexImage

def download_from_gcs(gcs_uri, local_path):
    """Download file from GCS to local path."""
    client = storage.Client()
    blob_path = gcs_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(local_path)

def write_json_to_gcs(blob_uri, data):
    """Write JSON to GCS blob."""
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(data, indent=2), content_type='application/json')

def analyze_brand_style(gcs_image_uris):
    """Use Gemini multimodal to analyze brand style."""
    if not gcs_image_uris:
        raise ValueError("No image URIs provided")

    prompt = """
Analyze these brand images and logos to extract the overall style and aesthetic.

Provide a comprehensive analysis including:
1. Dominant colors: Identify the top 5 most prominent colors with their hex codes and descriptive names
2. Font style: What type of fonts are used (e.g., serif, sans-serif, modern, etc.)
3. Tone of voice: What tone does the brand convey (e.g., professional, playful, luxurious)
4. Overall aesthetic: General description of the visual style

Output your response as a JSON object with exactly these keys:
- "dominant_colors": Array of objects, each with "hex_code" and "name"
- "font_style": String describing the font characteristics
- "tone_of_voice": String describing the brand tone
- "aesthetic": String describing the overall visual style

Keep each string description to 50 words or less.

Do not include any text outside the JSON.
"""

    # Load images
    images = []
    temp_files = []
    try:
        for gcs_uri in gcs_image_uris:
            temp_fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(gcs_uri)[-1])
            temp_files.append(temp_path)
            download_from_gcs(gcs_uri, temp_path)
            image = VertexImage.load_from_file(temp_path)
            images.append(image)

        # Initialize Vertex AI
        aiplatform.init(project=aiplatform.Config.get_project(), location=aiplatform.Config.get_location())
        model = GenerativeModel("gemini-pro-vision")

        # Create content parts
        content_parts = [prompt] + images

        response = model.generate_content(content_parts)
        response_text = response.text.strip()

        # Try to parse as JSON
        try:
            parsed = json.loads(response_text)
            return {
                "dominant_colors": parsed.get("dominant_colors", []),
                "font_style": parsed.get("font_style", ""),
                "tone_of_voice": parsed.get("tone_of_voice", ""),
                "aesthetic": parsed.get("aesthetic", "")
            }
        except json.JSONDecodeError:
            # Fallback
            return {
                "dominant_colors": [{"hex_code": "#000000", "name": "black"}],
                "font_style": response_text[:100],
                "tone_of_voice": "Unknown",
                "aesthetic": "Undetermined"
            }
    finally:
        # Clean up temp files
        for temp_path in temp_files:
            try:
                os.unlink(temp_path)
            except:
                pass

@functions_framework.http
def main_handler(request):
    """HTTP Cloud Function for brand style analysis."""
    json_data = request.get_json()
    if not json_data:
        return {'error': 'Invalid JSON body'}, 400

    # Extract parameters
    gcs_image_uris = json_data.get('gcs_image_uris')
    gcs_output_uri = json_data.get('gcs_output_uri')
    project = json_data.get('project')
    location = json_data.get('location')

    if not all([gcs_image_uris, gcs_output_uri, project]):
        return {'error': 'Missing required parameters'}, 400

    try:
        # Analyze style
        analysis = analyze_brand_style(gcs_image_uris)

        # Add metadata
        output_data = {
            "version": "1.0",
            "analysis": analysis
        }

        # Write output
        write_json_to_gcs(gcs_output_uri, output_data)

        return {'status': 'success', 'output_uri': gcs_output_uri}, 200

    except Exception as e:
        return {'error': str(e)}, 500
