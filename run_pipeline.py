import google.cloud.aiplatform as aip
import argparse
import json

def run_adapt_pipeline(
    project_id: str,
    location: str,
    pipeline_root: str,
    pipeline_json_path: str,
    product_data_uri: str,
    brand_creative_uris: list,
    veo_secret_id: str,
):
    """
    Submits a compiled KFP pipeline to Vertex AI Pipelines.

    Args:
        project_id: The GCP project ID.
        location: The GCP region for the pipeline run.
        pipeline_root: The GCS path for storing pipeline artifacts.
        pipeline_json_path: Local path to the compiled pipeline JSON file.
        product_data_uri: GCS URI of the product data file.
        brand_creative_uris: List of GCS URIs for brand images.
        veo_secret_id: The ID of the Veo API key secret in Secret Manager.
    """
    aip.init(project=project_id, location=location)

    job = aip.PipelineJob(
        display_name="adapt-ad-generation-run",
        template_path=pipeline_json_path,
        pipeline_root=pipeline_root,
        parameter_values={
            "project": project_id,
            "location": location,
            "gcs_root": pipeline_root,
            "gcs_product_data_uri": product_data_uri,
            "gcs_brand_creative_uris": brand_creative_uris,
            "veo_api_secret_id": veo_secret_id,
        },
        enable_caching=False # Use caching for production runs to save costs
    )

    print("Submitting pipeline job...")
    job.submit()
    print(f"Pipeline job submitted. View it in the console: {job.dashboard_uri}")
    print(f"Job Name: {job.resource_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", required=True, help="Your GCP project ID.")
    parser.add_argument("--location", default="us-central1", help="GCP region.")
    parser.add_argument("--pipeline_root", required=True, help="GCS path for pipeline artifacts (e.g., gs://your-bucket/pipelines).")
    parser.add_argument("--product_data_uri", required=True, help="GCS URI for the product data file.")
    parser.add_argument("--brand_creative_uris", required=True, help="JSON string of a list of GCS URIs for brand images.")
    parser.add_argument("--veo_secret_id", required=True, help="The ID of the Veo API key secret.")
    
    args = parser.parse_args()

    run_adapt_pipeline(
        project_id=args.project_id,
        location=args.location,
        pipeline_root=args.pipeline_root,
        pipeline_json_path="adapt_pipeline.json",
        product_data_uri=args.product_data_uri,
        brand_creative_uris=json.loads(args.brand_creative_uris),
        veo_secret_id=args.veo_secret_id,
    )