# AdAPT (Ad Prompt & Transformation) - Solution Architecture & User Guide

This document outlines the solution architecture for AdAPT, a pipeline designed to generate AI video ads from product and brand inputs, incorporating human-in-the-loop for quality control.

## 1. Solution Architecture

The architecture is built on Google Cloud, leveraging serverless components for scalability and managed services for operational efficiency.

### 1.1. High-Level Diagram

```
                               +--------------------------------+
                               |      Human-in-the-Loop UI      |
                               | (Cloud Run + Firebase/Firestore)|
                               +----------------+---------------+
                                                | (Approvals/Edits)
                                                |
  +------------------+           +--------------------------------+           +-----------------+
  |   Input Sources  |---------->|      AdAPT Core Pipeline       |---------->|  Final Outputs  |
  | - Product Text   |           |    (Vertex AI Pipelines)       |           | - Video Ad (MP4)|
  | - Brand Creatives|           +--------------------------------+           | - Ad Brief (JSON)|
  +------------------+                         |                               +-----------------+
                                               | (Executes Components)
                                               |
  +---------------------------------------------------------------------------------------------+
  |                                   Pipeline Components (Serverless)                          |
  |                                                                                             |
  | [1] Ingestion       [2a] USP Extraction    [2b] Style Analysis    [4] Ad Brief Gen.    [7] Video Gen. |
  | (Cloud Function)    (Cloud Function)       (Cloud Function)       (Cloud Function)     (Cloud Function)|
  |      |                   |                      |                      |                    |         |
  |      v                   v                      v                      v                    v         |
  | +---------+       +-----------------+    +-----------------+    +-----------------+    +----------+  |
  | | GCS     |       | Gemini Pro API  |    | Vision API      |    | Gemini Pro API  |    | Veo3 API |  |
  | | Bucket  |       +-----------------+    | Gemini Pro API  |    +-----------------+    +----------+  |
  | +---------+                              +-----------------+                                        |
  |                                                                                             |
  +---------------------------------------------------------------------------------------------+
```

### 1.2. Component Breakdown

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Workflow Orchestration** | **Vertex AI Pipelines** | Manages the entire end-to-end workflow, orchestrating component execution, handling data passing, and managing conditional logic for approvals. |
| **Input Storage** | **Cloud Storage (GCS)** | Securely stores all raw inputs (product data, images, logos) and generated artifacts (JSON briefs, final videos). |
| **Processing Components** | **Cloud Functions** | Each step in the pipeline (e.g., USP Extraction, Style Analysis) is encapsulated in a serverless Cloud Function. This allows for independent scaling and development. |
| **AI/ML Models** | **Vertex AI Model Garden** | Provides access to `Gemini Pro` for text/multimodal analysis and generation. The `Vision API` is used for specific image analysis tasks like color extraction. `Veo3` is the target for video generation. |
| **Human-in-the-Loop (HITL)** | **Cloud Run + Firestore** | A simple web UI hosted on Cloud Run allows human reviewers to approve or edit data. Firestore DB stores the state of review tasks and the edited data, triggering the pipeline to resume. |
| **API Gateway** | **API Gateway** | (Optional but recommended) Provides a secure, managed entry point for programmatic pipeline execution, handling authentication and rate limiting. |

---

## 2. Step-by-Step Technical Flow

This flow details the journey from data input to final video output, orchestrated by Vertex AI Pipelines.

1.  **Pipeline Trigger & Ingestion:**
    *   **Action:** A user accesses the AdAPT web UI, pastes product text, and uploads brand creative files directly into a form.
    *   **Process:** Upon submission, the UI's backend (a Cloud Run service) saves these inputs to a new, unique folder in GCS. It then programmatically validates the inputs and starts a new `Vertex AI Pipelines` run.
    *   **Outcome:** The pipeline is initiated with the GCS paths of the user-provided files as its starting parameters.

2.  **Parallel Processing (Components in Vertex AI Pipeline):**
    *   **A. USP & Emotion Extraction:**
        *   A Cloud Function component reads the product data from GCS.
        *   It calls the `Gemini Pro` API with a prompt to analyze the text, scrape any provided URLs for more context, and extract key Unique Selling Propositions (USPs) and potential emotional triggers.
        *   **Output:** A JSON object with extracted USPs and emotions is saved to GCS (e.g., `analysis_usp.json`).
    *   **B. Brand Style Analysis:**
        *   A Cloud Function component reads brand assets (images, logos) from GCS.
        *   It calls the `Gemini Pro` (multimodal) API with the brand assets. The prompt instructs the model to act as a brand expert, analyzing the overall style, font characteristics, tone of voice, and to extract the dominant color palette in a structured format.
        *   *(Alternative: For potentially higher accuracy and reliability in color extraction, the `Vision API` can be used specifically for that task, while Gemini handles the more subjective style analysis.)*
        *   **Output:** A JSON object with the complete style analysis is saved to GCS (e.g., `analysis_style.json`).

3.  **Human Approval & Refinement (Checkpoint 1):**
    *   **Action:** The pipeline pauses. It triggers a notification (e.g., Pub/Sub message or direct API call) to the HITL system.
    *   **HITL System:**
        *   The Cloud Run web app listens for new review tasks.
        *   It creates a new task entry in Firestore, linking to the `analysis_usp.json` and `analysis_style.json` files.
        *   The UI displays the extracted USPs, emotions, and style elements in a user-friendly, editable format.
    *   **Human Review:** A user reviews, edits, and approves the data via the web UI. On submission, the UI updates the Firestore document with the refined data and marks the task as 'approved'.
    *   **Resume Pipeline:** A Cloud Function triggered by the Firestore update calls the Vertex AI API to resume the paused pipeline run, providing the path to the *refined* data.

4.  **Ad Brief Generation:**
    *   **Action:** The resumed pipeline executes the `Ad Brief Generator` component.
    *   **Process:** This Cloud Function reads the *human-approved* USP and Style JSON data.
    *   It calls `Gemini Pro` with a structured prompt, instructing it to synthesize the inputs into a cohesive ad brief (hook, script, visual cues, CTA).
    *   **Output:** A structured `ad_brief.json` is generated and saved to GCS.

5.  **Video Prompt Conversion & Final Approval (Checkpoint 2):**
    *   **Action:** The pipeline converts the `ad_brief.json` into the specific JSON format required by the `Veo3` API.
    *   **Process:** This step can be a simple data transformation component.
    *   **HITL System:** The pipeline pauses again, presenting the final, structured `Veo3` prompt to the user for a go/no-go decision. This is a critical cost-control and brand safety step.
    *   **Human Review:** User gives final approval in the HITL UI.

6.  **Video Generation:**
    *   **Action:** Upon final approval, the pipeline executes the `Video Generation` component.
    *   **Process:** This Cloud Function reads the approved `Veo3` prompt JSON.
    *   It makes an authenticated API call to the `Veo3` endpoint. This will likely be an asynchronous job. The function can poll for completion or be triggered by a callback.
    *   **Output:** The generated video file is downloaded from the `Veo3` service and saved to the final output directory in the GCS bucket (e.g., `final_video.mp4`).

7.  **Pipeline Completion:** The pipeline run is marked as 'Succeeded'.

---

## 3. Data Schemas

Clear data contracts between components are crucial.

### 3.1. Ad Brief Schema (`ad_brief.json`)

This schema is the output of the Ad Brief Generator and serves as the creative foundation.

```json
{
  "campaignId": "campaign-xyz-123",
  "productId": "product-abc-456",
  "metadata": {
    "version": "1.0",
    "createdAt": "2023-10-27T10:00:00Z",
    "approvedBy": "user@example.com"
  },
  "creativeConcept": {
    "hook": "Tired of slow, unreliable Wi-Fi? Meet the future of connectivity.",
    "coreMessage": "Our new router delivers lightning-fast speeds for seamless streaming and gaming.",
    "callToAction": {
      "text": "Upgrade Now",
      "url": "https://example.com/product"
    }
  },
  "script": [
    {
      "scene": 1,
      "duration_seconds": 2,
      "visuals": "Close-up on a frustrated person looking at a buffering video on their laptop.",
      "voiceover": "Don't let buffering ruin your day."
    },
    {
      "scene": 2,
      "duration_seconds": 3,
      "visuals": "Dynamic shot of the sleek, modern router. Light pulses from its logo. The laptop screen now shows a 4K movie playing flawlessly.",
      "voiceover": "Experience the power of next-gen speed and reliability."
    }
  ],
  "styleGuidance": {
    "tone": "Energetic, Tech-forward, Confident",
    "dominantColors": ["#0A192F", "#64FFDA", "#CCD6F6"],
    "fontStyle": "Modern, sans-serif"
  }
}
```

### 3.2. Veo3 API Input Schema (`veo3_prompt.json`)

This is a hypothetical schema, structured for a video generation model.

```json
{
  "jobId": "video-gen-job-987",
  "output_format": {
    "resolution": "1920x1080",
    "duration_seconds": 5,
    "fps": 30
  },
  "style_reference": {
    "prompt": "A modern, energetic, and tech-forward commercial. Cinematic, with dynamic camera movements. Color palette: deep navy blue, vibrant teal, and off-white.",
    "logo_overlay": {
      "gcs_path": "gs://your-bucket/brand/logo.png",
      "position": "bottom_right"
    }
  },
  "scenes": [
    {
      "prompt": "Scene 1: A frustrated person looking at a buffering video on a laptop. The room is dimly lit. The mood is annoyance.",
      "duration_seconds": 2
    },
    {
      "prompt": "Scene 2: A sleek, modern Wi-Fi router on a clean desk. A teal light pulses from its logo. A 4K movie plays perfectly on the laptop in the background.",
      "duration_seconds": 3
    }
  ]
}
```

---

## 4. Scalability & Extensibility

*   **Scalability:** The serverless nature of Cloud Functions and the managed scaling of Vertex AI Pipelines ensure the system can handle fluctuating loads, from a single ad request to thousands.
*   **Multi-Brand/Campaign:**
    *   Use distinct GCS prefixes for each brand and campaign (e.g., `gs://bucket/brand_A/campaign_1/`).
    *   Store brand-specific style guides or pre-approved assets in their respective folders to be used as context in the pipeline.
    *   The `campaignId` and `brandId` can be passed as parameters to the pipeline, ensuring proper data segregation and tracking.
*   **Extensibility:**
    *   **New Models:** To swap `Veo3` for a new model, only the `Video Generation` component and the `Veo3 Prompt` schema need to be updated. The rest of the pipeline remains unchanged.
    *   **New Steps:** Adding a new step, like a legal compliance check, is as simple as creating a new Cloud Function component and inserting it into the Vertex AI Pipeline definition.

## 5. Security & Compliance

*   **Data Protection:**
    *   All brand data at rest in GCS is encrypted by default. Use Customer-Managed Encryption Keys (CMEK) for stricter control.
    *   Enable VPC Service Controls to create a service perimeter, preventing data exfiltration from your GCP project.
*   **Access Control:**
    *   Use Identity and Access Management (IAM) with the principle of least privilege. The Cloud Function for video generation should only have permissions to call the `Veo3` API, not to read from other projects.
    *   The HITL web app should authenticate users via Identity Platform or IAP (Identity-Aware Proxy) to ensure only authorized personnel can approve changes.
*   **API Security:**
    *   All calls to Google Cloud APIs (Gemini, Vision) should use service account credentials with tightly scoped IAM roles.
    *   Secure the `Veo3` API key using Secret Manager. The video generation Cloud Function will be granted IAM permission to access only this specific secret at runtime.

This architecture provides a robust foundation for your AdAPT project, balancing automation with essential human oversight while being designed for future growth and security.
