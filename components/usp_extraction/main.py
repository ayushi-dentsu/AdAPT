#!/usr/bin/env python3
"""
USP Extraction Component - Cloud Function
Extract Unique Selling Propositions and emotional triggers from product data using Gemini Pro.
"""

import functions_framework
import json
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

def extract_usp_emotion(product_data):
    """Use Gemini Pro to extract USPs and emotions."""
    # Assuming product_data is dict with 'product_description' key
    product_text = product_data.get("product_description", "")

    if not product_text:
        raise ValueError("Product data must contain 'product_description' field")

    prompt = f"""
Analyze the following product description and extract:
1. Unique Selling Propositions (USPs): What makes this product unique or better than competitors?
2. Potential emotional triggers: What emotions does this product evoke in customers?

Provide your response as a JSON object with exactly two keys:
- "usps": An array of up to 5 strings, each describing a USP
- "emotions": An array of up to 5 strings, each describing an emotional trigger

Product description: {product_text}

Respond only with valid JSON, no other text.
"""

    # Initialize Vertex AI
    aiplatform.init(project=aiplatform.Config.get_project(), location=aiplatform.Config.get_location())
    model = GenerativeModel("gemini-pro")

    response = model.generate_content(prompt=prompt)
    response_text = response.text.strip()

    # Try to parse as JSON
    try:
        parsed = json.loads(response_text)
        return {
            "usps": parsed.get("usps", []),
            "emotions": parsed.get("emotions", [])
        }
    except json.JSONDecodeError:
        # Fallback if model doesn't return valid JSON
        return {
            "usps": [response_text.split("\n")[0]],
            "emotions": []
        }

@functions_framework.http
def main_handler(request):
    """HTTP Cloud Function for USP extraction."""
    json_data = request.get_json()
    if not json_data:
        return {'error': 'Invalid JSON body'}, 400

    # Extract parameters
    gcs_product_data_uri = json_data.get('gcs_product_data_uri')
    gcs_output_uri = json_data.get('gcs_output_uri')
    project = json_data.get('project')
    location = json_data.get('location')

    if not all([gcs_product_data_uri, gcs_output_uri, project]):
        return {'error': 'Missing required parameters'}, 400

    try:
        # Read product data
        product_data = read_json_from_gcs(gcs_product_data_uri)

        # Extract USPs and emotions
        analysis = extract_usp_emotion(product_data)

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
