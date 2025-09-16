from kfp import dsl
from kfp.v2 import compiler
from google_cloud_pipeline_components.v1.wait_gcp_resources import WaitGcpResourcesOp

# --- Component Loading ---
# In a real-world scenario, you would have a CI/CD process to build and push these
# component definitions to a central repository. For this example, we load them from local files.

usp_extraction_op = dsl.load_component_from_file(
    'components/usp_extraction/component.yaml'
)
brand_style_analysis_op = dsl.load_component_from_file(
    'components/brand_style_analysis/component.yaml'
)
ad_brief_generator_op = dsl.load_component_from_file(
    'components/ad_brief_generator/component.yaml'
)
video_generator_op = dsl.load_component_from_file(
    'components/video_generator/component.yaml'
)


@dsl.pipeline(
    name='adapt-ad-generation-pipeline',
    description='Generates a video ad from product and brand inputs with human-in-the-loop checkpoints.'
)
def adapt_pipeline(
    project: str,
    location: str,
    gcs_root: str,
    gcs_product_data_uri: str,
    gcs_brand_creative_uris: list,
    veo_api_secret_id: str,
    pipeline_job_id: str = "{{$.pipeline_job_name}}",
):
    """
    The main pipeline definition for the AdAPT workflow.
    """
    # Define unique GCS paths for this pipeline run's artifacts
    run_gcs_root = dsl.ConcatPlaceholder(
        items=[gcs_root, "/", pipeline_job_id]
    )
    usp_output_path = dsl.ConcatPlaceholder(items=[run_gcs_root, "/analysis_usp.json"])
    style_output_path = dsl.ConcatPlaceholder(items=[run_gcs_root, "/analysis_style.json"])
    brief_output_path = dsl.ConcatPlaceholder(items=[run_gcs_root, "/ad_brief.json"])
    # This is a placeholder for the prompt that the user will approve/edit
    final_prompt_path = dsl.ConcatPlaceholder(items=[run_gcs_root, "/veo3_prompt_approved.json"])
    video_output_path = dsl.ConcatPlaceholder(items=[run_gcs_root, "/final_video.mp4"])

    # --- 1. Parallel Analysis Step ---
    usp_task = usp_extraction_op(
        project=project,
        location=location,
        gcs_product_data_uri=gcs_product_data_uri,
        gcs_output_uri=usp_output_path,
    )

    style_task = brand_style_analysis_op(
        project=project,
        location=location,
        gcs_image_uris=gcs_brand_creative_uris,
        gcs_output_uri=style_output_path,
    )

    # --- 2. First Human-in-the-Loop (HITL) Checkpoint ---
    # This step pauses the pipeline until the user approves the initial analyses.
    # The UI would read the outputs from usp_task and style_task, allow edits,
    # and then create a "gate" file in GCS to signal completion.
    approval_gate_1_uri = dsl.ConcatPlaceholder(items=[run_gcs_root, "/approval_gate_1.txt"])

    hitl_1_task = WaitGcpResourcesOp(
        gcp_resources=[approval_gate_1_uri]
    ).after(usp_task, style_task)

    # --- 3. Ad Brief Generation ---
    # This task runs only after the first approval is granted.
    brief_task = ad_brief_generator_op(
        project=project,
        location=location,
        gcs_usp_analysis_uri=usp_task.outputs["gcs_output_path"],
        gcs_style_analysis_uri=style_task.outputs["gcs_output_path"],
        gcs_output_uri=brief_output_path,
    ).after(hitl_1_task)

    # --- 4. Second Human-in-the-Loop (HITL) Checkpoint ---
    # This step pauses the pipeline for final approval of the video prompt.
    # The UI would read the generated ad brief, transform it into the Veo3 prompt format,
    # allow final user edits, and save it to `final_prompt_path`.
    # It then creates the second gate file.
    approval_gate_2_uri = dsl.ConcatPlaceholder(items=[run_gcs_root, "/approval_gate_2.txt"])

    hitl_2_task = WaitGcpResourcesOp(
        gcp_resources=[approval_gate_2_uri]
    ).after(brief_task)

    # --- 5. Final Video Generation ---
    # This runs only after the final go/no-go approval.
    video_task = video_generator_op(
        project=project,
        location=location,
        veo_api_secret_id=veo_api_secret_id,
        gcs_video_prompt_uri=final_prompt_path,
        gcs_output_uri=video_output_path,
    ).after(hitl_2_task)


if __name__ == '__main__':
    compiler.Compiler().compile(
        pipeline_func=adapt_pipeline,
        package_path='adapt_pipeline.json'
    )
