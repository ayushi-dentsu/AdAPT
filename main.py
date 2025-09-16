    if not all([gcs_prompt_uri, gcs_output_uri, project, secret_id]):
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
    # --- 2. Get API Key and Prompt Data ---
    try:
        api_key = get_api_key(project, secret_id)
        video_prompt = get_json_from_gcs(gcs_prompt_uri)
    except Exception as e:
        print(f"Error preparing for API call: {e}")
        return f"Error: Failed to get API key or prompt data. Details: {e}", 500

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
    # --- 3. Call Hypothetical Veo3 API ---
    # This section is an assumption of how a video generation API might work.
    # It likely involves starting a job and then polling for its result.
    VEO_API_ENDPOINT = "https://api.example.com/v1/video/jobs" # Hypothetical endpoint
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # --- 3. Commit the batch ---
    try:
        batch.commit()
        print(f"Successfully created HITL task documents for pipeline run: {pipeline_job_id}")
        return {"status": "success", "message": f"Documents created for {pipeline_job_id}"}, 201
    except Exception as e:
        print(f"Error committing to Firestore: {e}")
        return f"Error: Failed to create Firestore documents. Details: {e}", 500
        # Start the generation job
        start_response = requests.post(VEO_API_ENDPOINT, headers=headers, json=video_prompt)
        start_response.raise_for_status() # Raises an exception for 4xx/5xx status
        job_data = start_response.json()
        job_id = job_data.get("jobId")
        
        if not job_id:
            raise ValueError("API did not return a job ID.")

        # Poll for completion
        job_status_endpoint = f"{VEO_API_ENDPOINT}/{job_id}"
        status = ""
        video_url = None
        while status not in ["SUCCEEDED", "FAILED"]:
            time.sleep(10) # Wait before checking status again
            status_response = requests.get(job_status_endpoint, headers=headers)
            status_response.raise_for_status()
            status_data = status_response.json()
            status = status_data.get("status")
            print(f"Job {job_id} status: {status}")
            if status == "SUCCEEDED":
                video_url = status_data.get("outputUrl")

        if status == "FAILED" or not video_url:
            raise RuntimeError(f"Video generation job {job_id} failed.")

        # --- 4. Download Video and Save to GCS ---
        video_data = requests.get(video_url, stream=True)
        video_data.raise_for_status()

        storage_client = storage.Client()
        output_bucket_name, output_blob_name = parse_gcs_uri(gcs_output_uri)
        output_bucket = storage_client.bucket(output_bucket_name)
        output_blob = output_bucket.blob(output_blob_name)

        # Upload the video stream to GCS
        output_blob.upload_from_file(video_data.raw, content_type='video/mp4')

        print(f"Successfully generated and saved video to {gcs_output_uri}")
        return {"message": "Video generation complete", "output_path": gcs_output_uri}, 200

    except requests.exceptions.RequestException as e:
        print(f"Error calling Veo3 API: {e}")
        return f"Error: API call failed. Details: {e}", 502 # Bad Gateway
    except (ValueError, RuntimeError, Exception) as e:
        print(f"Error during video generation process: {e}")
        return f"Error: Video generation process failed. Details: {e}", 500