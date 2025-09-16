#!/usr/bin/env python3
"""
USP Extraction Component
Extract Unique Selling Propositions and emotional triggers from product data using Gemini Pro.
"""

import argparse
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gcs_product_data_uri', required=True, help='GCS URI of input product data JSON')
    parser.add_argument('--gcs_output_uri', required=True, help='GCS URI for output analysis JSON')
    parser.add_argument('--project', required=True, help='GCP project ID')
    parser.add_argument('--location', required=True, help='GCP location')

    args = parser.parse_args()

    # Read product data
    product_data = read_json_from_gcs(args.gcs_product_data_uri)

    # Extract USPs and emotions
    analysis = extract_usp_emotion(product_data)

    # Add metadata
    output_data = {
        "version": "1.0",
        "analysis": analysis
    }

    # Write output
    write_json_to_gcs(args.gcs_output_uri, output_data)

    print(f"USP and emotion extraction completed. Output saved to {args.gcs_output_uri}")

if __name__ == "__main__":
    main()
