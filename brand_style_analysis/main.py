import functions_framework
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

# Initialize Firebase Admin SDK
# This is done once per function instance
try:
    firebase_admin.initialize_app()
except ValueError:
    # App is already initialized, ignore the error
    pass

db = firestore.client()

@functions_framework.http
def initiate_hitl_task(request):
    """
    Creates the initial Firestore documents to track a new pipeline run and its first HITL task.

    Request JSON body:
    {
        "pipelineJobId": "pipelines-12345-abcde",
        "gcsRootPath": "gs://your-bucket/pipelines-12345-abcde",
        "userEmail": "user@example.com",
        "uspAnalysisUri": "gs://your-bucket/pipelines-12345-abcde/analysis_usp.json",
        "styleAnalysisUri": "gs://your-bucket/pipelines-12345-abcde/analysis_style.json",
        "gateFileUri": "gs://your-bucket/pipelines-12345-abcde/approval_gate_1.txt"
    }
    """
    request_json = request.get_json(silent=True)
    if not request_json:
        return "Error: Invalid JSON.", 400

    # --- 1. Get Parameters ---
    pipeline_job_id = request_json.get("pipelineJobId")
    gcs_root_path = request_json.get("gcsRootPath")
    user_email = request_json.get("userEmail")
    usp_uri = request_json.get("uspAnalysisUri")
    style_uri = request_json.get("styleAnalysisUri")
    gate_uri = request_json.get("gateFileUri")

    if not all([pipeline_job_id, gcs_root_path, user_email, usp_uri, style_uri, gate_uri]):
        return "Error: Missing required parameters.", 400

    # --- 2. Use a Firestore Batch to write documents atomically ---
    batch = db.batch()
    
    # Document 1: The main pipeline run document
    run_doc_ref = db.collection("pipeline_runs").document(pipeline_job_id)
    run_data = {
        "pipelineJobId": pipeline_job_id,
        "createdAt": datetime.now(timezone.utc),
        "createdBy": user_email,
        "status": "PENDING_APPROVAL",
        "gcsRootPath": gcs_root_path,
        "finalVideoPath": None
    }
    batch.set(run_doc_ref, run_data)

    # Document 2: The first HITL task document in the sub-collection
    task_doc_ref = run_doc_ref.collection("hitl_tasks").document("analysis_review")
    task_data = {
        "taskName": "analysis_review",
        "status": "PENDING",
        "createdAt": datetime.now(timezone.utc),
        "assignedTo": "creative_team@example.com", # Or dynamically assign
        "approvedBy": None,
        "approvedAt": None,
        "inputs": {
            "uspAnalysisUri": usp_uri,
            "styleAnalysisUri": style_uri
        },
        "outputs": {},
        "gateFileUri": gate_uri
    }
    batch.set(task_doc_ref, task_data)

    # --- 3. Commit the batch ---
    try:
        batch.commit()
        print(f"Successfully created HITL task documents for pipeline run: {pipeline_job_id}")
        return {"status": "success", "message": f"Documents created for {pipeline_job_id}"}, 201
    except Exception as e:
        print(f"Error committing to Firestore: {e}")
        return f"Error: Failed to create Firestore documents. Details: {e}", 500