#!/usr/bin/env python3
"""
Ad Brief Generator Component - Cloud Function
Generate a structured ad brief by synthesizing USP and style analysis using Gemini Pro.
"""

import functions_framework
import json
import uuid
from google.cloud import storage
from google.cloud import aiplatform
from vertexai.preview.generative_models import GenerativeModel

def read_json_from_gcs(blob_uri):
    """Read JSON from GCS blob."""
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    content = blob.download_as_text()
    return json.loads(content)

def write_json_to_gcs(blob_uri, data):
    """Write JSON to GCS blob."""
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(data, indent=2), content_type='application/json')

def generate_ad_brief(usp_analysis, style_analysis, campaign_id, product_id):
    """Use Gemini Pro to generate ad brief."""

    prompt = f"""
As a creative director, create a compelling ad brief for a video advertisement.

You have the following inputs:

USP & Emotion Analysis:
{json.dumps(usp_analysis.get("analysis", {}), indent=2)}

Brand Style Analysis:
{json.dumps(style_analysis.get("analysis", {}), indent=2)}

Campaign ID: {campaign_id}
Product ID: {product_id}

Generate a comprehensive ad brief following this exact JSON structure:

{{
  "campaignId": "{campaign_id}",
  "productId": "{product_id}",
  "metadata": {{
    "version": "1.0",
    "createdAt": "2024-XX-XXTXX:XX:XXZ",
    "approvedBy": null
  }},
  "creativeConcept": {{
    "hook": "A compelling opening hook (15-30 seconds)",
    "coreMessage": "The main message about the product benefits",
    "callToAction": {{
      "text": "Action-oriented CTA text",
      "url": "https://example.com/product"
    }}
  }},
  "script": [
    {{
      "scene": 1,
      "duration_seconds": 3,
      "visuals": "Description of visuals",
      "voiceover": "Voiceover text for this scene"
    }}
  ],
  "styleGuidance": {{
    "tone": "Emotional tone from analysis",
    "dominantColors": ["array of hex codes from style analysis"],
    "fontStyle": "Font style description from analysis"
  }}
}}

Fill in all fields appropriately based on the input analyses.
- Make the hook engaging and relevant to USPs
- Script should be 3-5 scenes total, each 2-4 seconds
- Use the emotions and tone of voice in creative decisions
- Output only the JSON, no other text.
"""

    # Initialize Vertex AI
    aiplatform.init(project=aiplatform.Config.get_project(), location=aiplatform.Config.get_location())
    model = GenerativeModel("gemini-pro")

    response = model.generate_content(prompt=prompt)
    response_text = response.text.strip()

    # Clean response (remove markdown code blocks if present)
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    response_text = response_text.strip()

    # Try to parse as JSON
    try:
        brief = json.loads(response_text)
        return brief
    except json.JSONDecodeError:
        # Fallback structure
        return {
            "campaignId": campaign_id,
            "productId": product_id,
            "metadata": {
                "version": "1.0",
                "createdAt": "2024-01-01T00:00:00Z",
                "approvedBy": None
            },
            "creativeConcept": {
                "hook": usp_analysis.get("analysis", {}).get("usps", [""])[:25],
                "coreMessage": "Check emotional triggers: " + ", ".join([str(x) for x in usp_analysis.get("analysis", {}).get("emotions", [])]),
                "callToAction": {
                    "text": "Learn More",
                    "url": "https://example.com/product"
                }
            },
            "script": [
                {
                    "scene": 1,
                    "duration_seconds": 5,
                    "visuals": "Default scene description",
                    "voiceover": "Default voiceover"
                }
            ],
            "styleGuidance": {
                "tone": style_analysis.get("analysis", {}).get("tone_of_voice", "Professional"),
                "dominantColors": ["#FFFFFF", "#000000"],
                "fontStyle": style_analysis.get("analysis", {}).get("font_style", "Sans-serif")
            }
        }

@functions_framework.http
def main_handler(request):
    """HTTP Cloud Function for ad brief generation."""
    json_data = request.get_json()
    if not json_data:
        return {'error': 'Invalid JSON body'}, 400

    # Extract parameters
    gcs_usp_analysis_uri = json_data.get('gcs_usp_analysis_uri')
    gcs_style_analysis_uri = json_data.get('gcs_style_analysis_uri')
    gcs_output_uri = json_data.get('gcs_output_uri')
    project = json_data.get('project')
    location = json_data.get('location')
    campaign_id = json_data.get('campaign_id', f"campaign-{uuid.uuid4().hex[:6]}")
    product_id = json_data.get('product_id', f"product-{uuid.uuid4().hex[:6]}")

    if not all([gcs_usp_analysis_uri, gcs_style_analysis_uri, gcs_output_uri, project]):
        return {'error': 'Missing required parameters'}, 400

    try:
        # Read inputs
        usp_analysis = read_json_from_gcs(gcs_usp_analysis_uri)
        style_analysis = read_json_from_gcs(gcs_style_analysis_uri)

        # Generate brief
        brief = generate_ad_brief(usp_analysis, style_analysis, campaign_id, product_id)

        # Write output
        write_json_to_gcs(gcs_output_uri, brief)

        return {'status': 'success', 'output_uri': gcs_output_uri}, 200

    except Exception as e:
        return {'error': str(e)}, 500
