#!/usr/bin/env python3
"""
Video Generator Component
Generate video ad using Veo3 API based on the approved video prompt.
"""

import argparse
import json
import time
import requests
import os
from google.cloud import storage

def read_json_from_gcs(blob_uri):
    """Read JSON from GCS blob."""
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    content = blob.download_as_text()
    return json.loads(content)

def download_to_gcs_from_url(url, gcs_uri):
    """Download file from URL and upload to GCS."""
    client = storage.Client()
    blob_path = gcs_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    response = requests.get(url, stream=True)
    response.raise_for_status()

    blob.upload_from_file(response.raw, content_type='video/mp4')

def generate_video(video_prompt, api_key):
    """Call Veo3 API to generate video."""
    VEO_API_ENDPOINT = "https://api.example.com/v1/video/jobs"  # Hypothetical endpoint - replace with actual Veo3 API
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Start the generation job
    start_response = requests.post(VEO_API_ENDPOINT, headers=headers, json=video_prompt)
    start_response.raise_for_status()
    job_data = start_response.json()
    job_id = job_data.get("jobId")

    if not job_id:
        raise ValueError("API did not return a job ID.")

    # Poll for completion
    job_status_endpoint = f"{VEO_API_ENDPOINT}/{job_id}"
    status = ""
    video_url = None
    while status not in ["SUCCEEDED", "FAILED"]:
        time.sleep(60)  # Wait 60 seconds before checking status
        status_response = requests.get(job_status_endpoint, headers=headers)
        status_response.raise_for_status()
        status_data = status_response.json()
        status = status_data.get("status")
        print(f"Job {job_id} status: {status}")
        if status == "SUCCEEDED":
            video_url = status_data.get("outputUrl")

    if status == "FAILED" or not video_url:
        raise RuntimeError(f"Video generation job {job_id} failed.")

    return video_url

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gcs_video_prompt_uri', required=True, help='GCS URI of video prompt JSON')
    parser.add_argument('--gcs_output_uri', required=True, help='GCS URI for output video MP4')
    parser.add_argument('--veo_api_secret_id', required=True, help='Secret ID for Veo3 API key')
    parser.add_argument('--project', required=True, help='GCP project ID')
    parser.add_argument('--location', required=True, help='GCP location')

    args = parser.parse_args()

    # Get API key from environment variable
    api_key = os.environ.get('VEO3_API_KEY')
    if not api_key:
        raise ValueError("VEO3_API_KEY environment variable not set")

    # Read video prompt
    video_prompt = read_json_from_gcs(args.gcs_video_prompt_uri)

    # Generate video
    video_url = generate_video(video_prompt, api_key)

    # Download to GCS
    download_to_gcs_from_url(video_url, args.gcs_output_uri)

    print(f"Video generation completed. Output saved to {args.gcs_output_uri}")

if __name__ == "__main__":
    main()
