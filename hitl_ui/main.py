from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import os
from google.cloud import storage
from google.cloud import aiplatform
from vertexai.preview.generative_models import GenerativeModel
import json
from datetime import datetime, timezone

# Initialize Flask
app = Flask(__name__)

# Initialize Firebase Admin SDK
try:
    firebase_admin.initialize_app()
except ValueError:
    # App is already initialized
    pass

db = firestore.client()

@app.route('/')
def index():
    """List all pending HITL tasks."""
    tasks_ref = db.collection_group('hitl_tasks').where('status', '==', 'PENDING')
    docs = tasks_ref.stream()
    tasks = []
    for doc in docs:
        data = doc.to_dict()
        data['pipeline_job_id'] = doc.reference.parent.parent.id
        data['task_name'] = doc.id
        tasks.append(data)
    return render_template('index.html', tasks=tasks)

@app.route('/task/<pipeline_job_id>/<task_name>', methods=['GET', 'POST'])
def task_details(pipeline_job_id, task_name):
    """View/Edit HITL task."""
    # Get task document
    run_ref = db.collection("pipeline_runs").document(pipeline_job_id)
    task_ref = run_ref.collection('hitl_tasks').document(task_name)
    task_doc = task_ref.get()
    if not task_doc.exists:
        return "Task not found", 404

    task_data = task_doc.to_dict()
    gate_uri = task_data.get('gateFileUri', '')

    if request.method == 'GET':
        inputs = task_data.get('inputs', {})
        # Read input files from GCS
        usp_analysis = read_json_from_gcs(inputs.get('uspAnalysisUri', ''))
        style_analysis = read_json_from_gcs(inputs.get('styleAnalysisUri', ''))
        # For ad_brief if second task
        if task_name != 'analysis_review':
            ad_brief = read_json_from_gcs(inputs.get('adBriefUri', ''))
            return render_template('approval_form.html', task=task_data, usp=usp_analysis, style=style_analysis, brief=ad_brief)
        else:
            return render_template('approval_form.html', task=task_data, usp=usp_analysis, style=style_analysis)

    else: # POST
        # Get the form data, edited
        edited_usp = request.form.get('usp')
        edited_style = request.form.get('style')
        approved_by = request.form.get('approved_by')

        # Update Firestore
        batch = db.batch()
        batch.update(task_ref, {
            'status': 'COMPLETED',
            'approvedBy': approved_by,
            'approvedAt': datetime.now(timezone.utc),
            'outputs': {
                'uspAnalysisUri': save_json_to_gcs(edited_usp, 'analysis_usp_approved.json'),
                'styleAnalysisUri': save_json_to_gcs(edited_style, 'analysis_style_approved.json')
            }
        })
        batch.commit()

        # For second HITL, generate Veo3 prompt
        if task_name != 'analysis_review':
            edited_brief = request.form.get('brief')
            vedo3_prompt = generate_veo3_prompt(edited_brief)
            # Save to final_prompt_path
            final_prompt_uri = request.form.get('final_prompt_uri')
            save_json_to_gcs_updated(vedo3_prompt, final_prompt_uri)

        # Create gate file
        create_gate_file(gate_uri)

        return "Approved and processed.", 200

def read_json_from_gcs(blob_uri):
    if not blob_uri:
        return {}
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    try:
        content = blob.download_as_text()
        return json.loads(content)
    except:
        return {}

def save_json_to_gcs(json_string, filename):
    # Placeholder, return dummy URI
    return f"gs://bucket/{filename}"

def create_gate_file(blob_uri):
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string("approved", content_type='text/plain')

def save_json_to_gcs_updated(data_dict, blob_uri):
    data = json.dumps(data_dict, indent=2)
    client = storage.Client()
    blob_path = blob_uri.replace("gs://", "")
    bucket_name, blob_name = blob_path.split("/", 1)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type='application/json')

def generate_veo3_prompt(ad_brief_string):
    """Use Gemini to convert ad_brief to Veo3 format."""
    prompt = f"""
Convert the following ad brief to the Veo3 API format.

Ad Brief:
{ad_brief_string}

Generate a JSON object in Veo3 format with:
- jobId
- output_format (resolution, duration, fps)
- style_reference (prompt with color palette)
- scenes (array of scene prompts and durations)

Make sure to embed the color palette and style into the style_reference.prompt.

Output only JSON.
"""

    aiplatform.init(project=os.environ.get('PROJECT_ID'), location='us-central1')
    model = GenerativeModel("gemini-pro")
    response = model.generate_content(prompt=prompt)
    return json.loads(response.text.strip())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
