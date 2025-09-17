import os
import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from google import genai
import uuid
from PIL import Image
import io
import time
from google.genai import types

# --- Configuration ---
PROJECT_ID = "vdc200015-ai-cxm-2-np"  # @param {type:"string"}
LOCATION = "us-central1"  # @param {type:"string"}
GCS_BUCKET_NAME = "team-12-bucket-1" # @param {type:"string"}
# Note: Replace with the actual Veo3 model name when available
#VIDEO_MODEL_NAME = "veo-3.0-generate-preview" # @param {type:"string"}
VIDEO_MODEL_NAME = "veo-3.0-generate-001"


# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Create static/videos directory if it doesn't exist
if not os.path.exists('static/videos'):
    os.makedirs('static/videos')

# --- Data Loading ---
creatives_df = pd.read_csv('Project Dataset - Sheet1.csv')

# --- Vertex AI Initialization ---
# This uses Application Default Credentials (ADC).
# You must be authenticated via `gcloud auth application-default login`.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
client = genai.Client(project=PROJECT_ID, location=LOCATION)


# --- Helper Functions ---

def scrape_url(url):
    """Scrapes the text content from a given URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        return " ".join(soup.stripped_strings)
    except requests.RequestException as e:
        print(f"Error scraping URL {url}: {e}")
        return f"Could not scrape URL: {e}"

def get_ai_analysis(prompt_text, image_url, scraped_text=""):
    """
    Analyzes text, an image, and scraped web content using Gemini Pro Vision.
    """
    prompt = f"""
    You are an expert brand strategist. Your task is to analyze the provided product information, brand creative, and website content.
    You must base your analysis *only* on the provided text and image. Do not invent or infer any information not present in the source material.

    **Source Materials:**
    - **Ad Creative Title:** "{prompt_text}"
    - **Scraped Website Content:** "{scraped_text[:2000]}"  # Limit context size
    - **Brand Creative:** [Image]

    **Your Analysis Task:**
    1.  **Extract USPs & Emotions:** Identify 3-5 unique selling propositions (USPs) and the primary emotions the ad should evoke.
    2.  **Analyze Brand Style:** Describe the brand's style, tone of voice, and dominant color palette based on the image.

    **Output Requirement:**
    Return a single, valid JSON object with the following structure. Do not include any explanatory text before or after the JSON object.
    {{
      "usps": ["usp1", "usp2", ...],
      "emotions": ["emotion1", "emotion2", ...],
      "style_analysis": {{
        "tone": "...",
        "dominant_colors": ["#hex1", "#hex2", ...],
        "font_style": "..."
      }}
    }}
    """
    
    try:
        content_parts = [prompt]
        
        if image_url:
            try:
                # Download the image from the URL
                print(f"Downloading image from URL: {image_url}")
                image_response = requests.get(image_url, timeout=10)
                image_response.raise_for_status()
                
                # Create the image part from the downloaded data
                print("Creating image part from downloaded data...")
                image = Image.open(io.BytesIO(image_response.content))
                content_parts.append(image)
                
            except requests.RequestException as img_e:
                print(f"Could not download image from {image_url}: {img_e}")
                # Optionally, you could pass an error message to the prompt
                # prompt += "\n\nNote: The brand creative image could not be loaded."

        print("Sending request to Vertex AI...")
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=content_parts
        )
        
        print("Parsing JSON response...")
        # Clean the response to remove markdown code block formatting
        cleaned_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        result = json.loads(cleaned_text)
        print("✓ AI Analysis completed successfully")
        return result
        
    except json.JSONDecodeError as e:
        error_details = {
            "error_type": "JSON_PARSE_ERROR",
            "message": f"AI returned invalid JSON format: {str(e)}",
            "raw_response": getattr(response, 'text', 'No response text available'),
            "suggestion": "The AI model returned text that isn't valid JSON. This might be due to the prompt or model limitations."
        }
        print(f"JSON Parse Error: {error_details}")
        return {"error": error_details}
        
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        
        # Categorize common errors
        if "404" in error_message and "Publisher Model" in error_message:
            error_details = {
                "error_type": "MODEL_NOT_FOUND",
                "message": f"The Gemini model 'gemini-2.5-pro' is not available in your project",
                "full_error": error_message,
                "suggestion": "Try using 'gemini-1.5-pro' or 'gemini-1.0-pro-vision' instead, or check if the model is enabled in your project."
            }
        elif "403" in error_message or "PERMISSION_DENIED" in error_message:
            error_details = {
                "error_type": "PERMISSION_DENIED",
                "message": "Your account doesn't have permission to use Vertex AI",
                "full_error": error_message,
                "suggestion": "Run 'gcloud auth application-default login' and ensure your account has the 'Vertex AI User' role."
            }
        elif "401" in error_message or "UNAUTHENTICATED" in error_message:
            error_details = {
                "error_type": "AUTHENTICATION_ERROR",
                "message": "Authentication failed",
                "full_error": error_message,
                "suggestion": "Run 'gcloud auth application-default login' to authenticate."
            }
        else:
            error_details = {
                "error_type": error_type,
                "message": f"Unexpected error during AI analysis: {error_message}",
                "full_error": error_message,
                "suggestion": "Check your network connection and Vertex AI service status."
            }
        
        print(f"Vertex AI Error ({error_type}): {error_details}")
        return {"error": error_details}

def generate_ad_brief(analysis_data):
    """
    Generates a structured ad brief from the AI analysis.
    """
    analysis_str = json.dumps(analysis_data, indent=2)
    prompt = f"""
    You are an award-winning creative director. Your task is to synthesize the provided analysis into a cohesive and compelling ad brief.
    Generate the script using *only* the information from the provided Analysis Data. Do not add new concepts, features, or ideas.

    **Analysis Data:**
    {analysis_str}

    **Your Task:**
    Create a complete ad brief that logically connects the hook to the core message and ends with a strong call to action. The script should be exactly two scenes.

    **Output Requirement:**
    Return a single, valid JSON object following this exact schema. Do not include any explanatory text before or after the JSON object.
    {{
      "creativeConcept": {{
        "hook": "...",
        "coreMessage": "...",
        "callToAction": {{ "text": "...", "url": "https://example.com" }}
      }},
      "script": [
        {{ "scene": 1, "duration_seconds": 2, "visuals": "...", "voiceover": "..." }},
        {{ "scene": 2, "duration_seconds": 3, "visuals": "...", "voiceover": "..." }}
      ]
    }}
    """
    
    try:
        print("Sending ad brief generation request to Vertex AI...")
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt
        )
        
        print("Parsing ad brief JSON response...")
        # Clean the response to remove markdown code block formatting
        cleaned_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
        result = json.loads(cleaned_text)
        print("✓ Ad Brief generation completed successfully")
        return result
        
    except json.JSONDecodeError as e:
        error_details = {
            "error_type": "JSON_PARSE_ERROR",
            "message": f"AI returned invalid JSON format for ad brief: {str(e)}",
            "raw_response": getattr(response, 'text', 'No response text available'),
            "suggestion": "The AI model didn't return valid JSON. Try simplifying the analysis data or check if the model is responding correctly."
        }
        print(f"Ad Brief JSON Parse Error: {error_details}")
        return {"error": error_details}
        
    except Exception as e:
        error_type = type(e).__name__
        error_message = str(e)
        
        # Categorize common errors for ad brief generation
        if "404" in error_message and "Publisher Model" in error_message:
            error_details = {
                "error_type": "MODEL_NOT_FOUND",
                "message": f"The Gemini model 'gemini-2.5-pro' is not available for ad brief generation",
                "full_error": error_message,
                "suggestion": "Try using 'gemini-1.5-pro' or 'gemini-1.0-pro' instead, or check if the model is enabled in your project."
            }
        elif "403" in error_message or "PERMISSION_DENIED" in error_message:
            error_details = {
                "error_type": "PERMISSION_DENIED",
                "message": "Permission denied while generating ad brief",
                "full_error": error_message,
                "suggestion": "Ensure your account has the 'Vertex AI User' role for this project."
            }
        elif "401" in error_message or "UNAUTHENTICATED" in error_message:
            error_details = {
                "error_type": "AUTHENTICATION_ERROR",
                "message": "Authentication failed during ad brief generation",
                "full_error": error_message,
                "suggestion": "Run 'gcloud auth application-default login' to re-authenticate."
            }
        else:
            error_details = {
                "error_type": error_type,
                "message": f"Unexpected error during ad brief generation: {error_message}",
                "full_error": error_message,
                "suggestion": "Check your network connection and try again."
            }
        
        print(f"Ad Brief Generation Error ({error_type}): {error_details}")
        return {"error": error_details}

def generate_video(final_brief):
    """
    Generates a video using the Vertex AI video model and saves it locally.
    """
    scenes = final_brief.get('script', [])
    style_analysis = final_brief.get('styleGuidance', {})
    
    # Enhanced prompt construction
    style_prompt = (
        f"A {style_analysis.get('tone', 'modern and energetic')} commercial. "
        f"The dominant color palette is {', '.join(style_analysis.get('dominantColors', []))}. "
        "The overall style is cinematic, photorealistic, 4k resolution, with professional color grading and dynamic camera movement. "
        "The scenes must flow together seamlessly with smooth transitions, creating a single, cohesive narrative."
    )
    
    # Create detailed scene descriptions
    scene_prompts = []
    for i, scene in enumerate(scenes):
        scene_prompts.append(f"Scene {i+1}: {scene.get('visuals', '')}")
    visual_descriptions = " ".join(scene_prompts)

    full_prompt = f"{style_prompt} The story unfolds as follows: {visual_descriptions}"

    print("--- Generating Video with Vertex AI ---")
    print(f"Enhanced Prompt: {full_prompt}")

    try:
        duration_seconds = sum(scene.get('duration_seconds', 0) for scene in scenes)
        print("Starting asynchronous video generation...")
        operation = client.models.generate_videos(
            model=VIDEO_MODEL_NAME,
            prompt=full_prompt,
            config=types.GenerateVideosConfig(
                aspectRatio="16:9",
                durationSeconds=duration_seconds,
                enhancePrompt=True,
                generateAudio=True,
                negativePrompt="wrong spellings",
                resolution="720p"
            )
        )

        print("Polling for video generation status...")
        while not operation.done:
            print("Waiting for video generation to complete...")
            time.sleep(10)
            operation = client.operations.get(operation)

        print("✓ Video generation operation complete.")
        
        video = operation.response.generated_videos[0]
        filename = f"video-ad-{uuid.uuid4().hex}.mp4"
        filepath = os.path.join('static', 'videos', filename)
        
        print(f"Saving video to local path: {filepath}")
        video.video.save(filepath)
        print("✓ Video saved successfully.")

        return {
            "status": "success",
            "video_url": filename,  # Return just the filename
            "message": "Video generated and saved successfully."
        }
            
    except Exception as e:
        print(f"Error during video generation: {e}")
        return {
            "status": "error",
            "message": f"An error occurred during video generation: {e}"
        }

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        creative_id = int(request.form['creative_id'])
        
        selected_creative = creatives_df.iloc[creative_id].fillna('')
        brand_url = str(selected_creative['Link url'])
        
        session['creative_title'] = str(selected_creative['Creative Title'])
        session['image_url'] = str(selected_creative['Ad creative url'])
        
        # 1. Scrape URL and Get AI Analysis
        print("--- Step 1: Getting Initial AI Analysis ---")
        scraped_text = scrape_url(brand_url)
        analysis = get_ai_analysis(session['creative_title'], session['image_url'], scraped_text)
        
        # Check if we got an error from the AI analysis
        if "error" in analysis:
            return render_template('index.html', 
                                 creatives=creatives_df.to_dict(orient='records'), 
                                 error_details=analysis["error"])
        
        # Check if we got a valid analysis response
        if "usps" not in analysis:
            fallback_error = {
                "error_type": "INVALID_RESPONSE",
                "message": "AI analysis did not return the expected data structure",
                "full_error": f"Raw response: {json.dumps(analysis)}",
                "suggestion": "The AI model may not be working correctly. Try again or check if the model is available."
            }
            return render_template('index.html', 
                                 creatives=creatives_df.to_dict(orient='records'), 
                                 error_details=fallback_error)

        session['analysis_data'] = analysis
        print(f"--- Analysis Received: {json.dumps(analysis, indent=2)} ---")
        
        return redirect(url_for('analysis_review'))
        
    return render_template('index.html', creatives=creatives_df.to_dict(orient='records'), error=None)

@app.route('/analysis-review')
def analysis_review():
    if 'analysis_data' not in session:
        return redirect(url_for('index'))
    
    analysis_data = session['analysis_data']
    # Pass the dictionary directly to the template
    return render_template('analysis_review.html', analysis_data=analysis_data)

@app.route('/generate-brief', methods=['POST'])
def generate_brief_route():
    if 'analysis_data' not in session:
        return redirect(url_for('index'))

    # Reconstruct the analysis data from the form
    # This is the new HITL step where we take user edits
    refined_analysis = {
        "usps": [usp.strip() for usp in request.form.get('usps', '').splitlines() if usp.strip()],
        "emotions": [emotion.strip() for emotion in request.form.get('emotions', '').splitlines() if emotion.strip()],
        "style_analysis": {
            "tone": request.form.get('tone', ''),
            "dominant_colors": request.form.getlist('dominant_colors'), # .getlist() is crucial for multiple values
            "font_style": request.form.get('font_style', '')
        }
    }
    
    # Update the session with the refined data for consistency
    session['analysis_data'] = refined_analysis
    print(f"--- Refined Analysis Received: {json.dumps(refined_analysis, indent=2)} ---")

    print("--- Step 2: Generating Ad Brief from Refined Data ---")
    ad_brief = generate_ad_brief(refined_analysis)

    if "error" in ad_brief:
        # This could happen if the second call fails. Show detailed error.
        return render_template('index.html', 
                             creatives=creatives_df.to_dict(orient='records'), 
                             error_details=ad_brief["error"])

    session['ad_brief'] = ad_brief
    print(f"--- Ad Brief Generated: {json.dumps(ad_brief, indent=2)} ---")
    
    return redirect(url_for('approval'))

@app.route('/get-creative-details/<int:creative_id>')
def get_creative_details(creative_id):
    if 0 <= creative_id < len(creatives_df):
        creative = creatives_df.iloc[creative_id].fillna('')
        return jsonify({
            'creative_title': creative['Creative Title'],
            'image_url': creative['Ad creative url'],
            'link_url': creative['Link url']
        })
    return jsonify({'error': 'Invalid creative ID'}), 404

@app.route('/approval', methods=['GET', 'POST'])
def approval():
    if 'ad_brief' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 3. Capture Human Edits and Finalize Brief
        final_brief = {
            "creativeConcept": {
                "hook": request.form['hook'],
                "coreMessage": request.form['coreMessage'],
                "callToAction": {
                    "text": request.form['cta_text'],
                    "url": request.form['cta_url']
                }
            },
            "script": [
                {
                    "scene": 1,
                    "duration_seconds": int(request.form['scene1_duration']),
                    "visuals": request.form['scene1_visuals'],
                    "voiceover": request.form['scene1_voiceover']
                },
                {
                    "scene": 2,
                    "duration_seconds": int(request.form['scene2_duration']),
                    "visuals": request.form['scene2_visuals'],
                    "voiceover": request.form['scene2_voiceover']
                }
            ],
            # Carry over the original style guidance
            "styleGuidance": session.get('analysis_data', {}).get('style_analysis', {})
        }
        session['final_brief'] = final_brief
        
        # 4. Generate Video
        print("--- Step 4: Generating Video ---")
        video_result = generate_video(final_brief)
        session['video_result'] = video_result
        
        return redirect(url_for('result'))

    ad_brief = session['ad_brief']
    style_analysis = session.get('analysis_data', {}).get('style_analysis', {})
    return render_template('approval.html', ad_brief=ad_brief, style_analysis=style_analysis)

@app.route('/result')
def result():
    if 'video_result' not in session:
        return redirect(url_for('index'))
        
    return render_template('result.html', video_result=session['video_result'])

if __name__ == '__main__':
    app.run(debug=True, port=5001)
