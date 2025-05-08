import os
import time
import json
import requests
import uuid
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# Load environment variables
load_dotenv()

# Suno API settings
SUNO_API_KEY = os.getenv("SUNO_API_KEY")
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:5001/callback")
BASE_URL = "https://apibox.erweima.ai"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def call_suno_api(endpoint, data, max_retries=3, retry_delay=5):
    """
    Common function to call Suno API (with retry functionality)
    
    Args:
        endpoint: API endpoint
        data: Request data
        max_retries: Maximum number of retries
        retry_delay: Delay between retries (seconds)
        
    Returns:
        API response
    """
    retry_count = 0
    last_exception = None
    
    while retry_count < max_retries:
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {SUNO_API_KEY}"
            }
            
            print(f"Calling Suno API: {BASE_URL}{endpoint} (Attempt {retry_count + 1}/{max_retries})")
            print(f"Request data: {json.dumps(data, ensure_ascii=False)}")
            
            response = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=data, timeout=60)
            
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text[:500]}...")  # Truncate long responses
            
            # Retry on 503 error
            if response.status_code == 503:
                retry_count += 1
                print(f"Received 503 error. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                continue
                
            if response.status_code != 200:
                print(f"ERROR: API returned status code {response.status_code}")
                raise Exception(f"API returned status code {response.status_code}: {response.text}")
                
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                print(f"ERROR: Failed to parse JSON response: {str(e)}")
                print(f"Response text: {response.text}")
                raise Exception(f"Failed to parse JSON response: {str(e)}")
            
            # Check for API errors based on response format
            if result.get("code") != 200:
                error_msg = f"API error: {result.get('msg')}"
                print(f"ERROR: {error_msg}")
                raise Exception(error_msg)
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Request failed: {str(e)}")
            last_exception = Exception(f"Request failed: {str(e)}")
            retry_count += 1
            print(f"Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(retry_delay)
        except Exception as e:
            print(f"ERROR: {str(e)}")
            last_exception = e
            retry_count += 1
            print(f"Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(retry_delay)
    
    # If all retries failed
    if last_exception:
        raise last_exception
    else:
        raise Exception("Maximum retries exceeded")

def generate_music_with_suno(prompt, reference_style=None, with_lyrics=True, model_version="v4", wait_for_completion=False, max_wait_time=300):
    """
    Function to generate music using Suno API
    
    Args:
        prompt: Music generation prompt
        reference_style: Reference style (genre etc.)
        with_lyrics: Whether to include lyrics (default: True)
        model_version: Model version (v3.5, v4 etc.)
        wait_for_completion: Whether to wait for generation completion
        max_wait_time: Maximum wait time (seconds)
        
    Returns:
        Dictionary containing generated music information or error information
    """
    try:
        print(f"\nGenerating music with Suno API...")
        print(f"Prompt: '{prompt}'")
        print(f"Reference style: {reference_style}")
        print(f"With lyrics: {with_lyrics}")
        print(f"Model version: {model_version}")
        print(f"Wait for completion: {wait_for_completion}")
        
        # Check API key
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return {"error": "SUNO_API_KEY is not set in environment variables"}
            
        print(f"SUNO_API_KEY: {SUNO_API_KEY[:5]}...{SUNO_API_KEY[-5:] if SUNO_API_KEY else ''}")
        
        # API endpoint
        api_endpoint = "/api/v1/generate"
        
        # Model version format - correction
        # Convert to exact format accepted by Suno API
        if model_version.lower() == "v3.5" or model_version.lower() == "v3_5" or model_version == "3.5":
            formatted_model = "V3_5"  # Capital V, underscore
        elif model_version.lower() == "v4" or model_version == "4":
            formatted_model = "V4"    # Capital V
        else:
            # Default to V4
            formatted_model = "V4"
            
        print(f"Formatted model: {formatted_model}")
        
        # Generate task ID (unique identifier)
        request_task_id = str(uuid.uuid4())
        
        # Set callback URL
        callback_url = CALLBACK_URL + "/api/callback/generate/music"
        # Ensure https (Suno callback requires https)
        if not callback_url.startswith("https://"):
            callback_url = callback_url.replace("http://", "https://")
        print(f"Using callback URL: {callback_url}")
        # Check callback URL for local development environment
        if "localhost" in callback_url or "127.0.0.1" in callback_url:
            print(f"Warning: Callback to local URL may not be reachable from outside: {callback_url}")
            print("Consider using a tunneling service like ngrok")
        
        print(f"Callback URL: {callback_url}")
        
        # For music with lyrics, add lyrics instruction to prompt
        enhanced_prompt = prompt
        if with_lyrics and "歌詞" not in prompt and "lyrics" not in prompt.lower():
            # If prompt doesn't mention lyrics, add instruction automatically
            if "日本語" in prompt or "Japanese" in prompt:
                enhanced_prompt += "。日本語の歌詞を含めてください。"
            else:
                enhanced_prompt += ". "
            print(f"Enhanced prompt for lyrics: '{enhanced_prompt}'")
        
        # Prepare request data (correct format based on Suno API documentation)
        data = {
            "prompt": enhanced_prompt,
            "style": reference_style if reference_style else "",
            "title": f"Generated Music {request_task_id[:8]}",
            "customMode": True,
            "instrumental": not with_lyrics,
            "model": formatted_model,
            "taskId": request_task_id,
            "callBackUrl": callback_url
        }
        
        # Add negative tags if available (optional)
        negative_tags = os.getenv("SUNO_NEGATIVE_TAGS", "")
        if negative_tags:
            data["negativeTags"] = negative_tags
        
        print(f"Request data: {json.dumps(data, ensure_ascii=False)}")
        
        # Send API request
        try:
            response_data = call_suno_api(api_endpoint, data)
            print(f"Response data: {json.dumps(response_data, ensure_ascii=False)}")
            
            # Process successful response
            if response_data.get("code") == 200:
                # Get taskId from response
                response_task_id = response_data.get("data", {}).get("taskId")
                if not response_task_id:
                    raise Exception("No taskId in response")
                
                result = {
                    "success": True,
                    "status": "pending",
                    "request_task_id": request_task_id,
                    "response_task_id": response_task_id,
                    "message": "Music generation request submitted successfully"
                }
                
                return result
            else:
                return {
                    "error": "API request failed",
                    "details": response_data
                }
        except Exception as api_error:
            print(f"API call failed: {str(api_error)}")
            return {
                "error": f"API call failed: {str(api_error)}"
            }
    
    except Exception as e:
        print(f"Error generating music: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return {
            "error": f"An error occurred: {str(e)}"
        }

def check_generation_status(task_id):
    """
    Function to check task status
    
    Args:
        task_id: Task ID
        
    Returns:
        Task status information
    """
    try:
        print(f"\nChecking status for task {task_id}...")
        
        # Check API key
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return None
        
        # Prepare request data
        data = {
            "taskId": task_id
        }
        
        # Call status check API - use correct endpoint
        result = call_suno_api("/api/v1/status", data, max_retries=1)
        
        # Get data from response
        response_data = result.get("data", {})
        
        print(f"Status response: {json.dumps(response_data, ensure_ascii=False)}")
        
        return response_data
        
    except Exception as e:
        print(f"Error checking status: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_wav_format(task_id):
    """
    Function to get WAV format of generated music
    
    Args:
        task_id: Task ID
        
    Returns:
        WAV format URL
    """
    try:
        print(f"\nGetting WAV format for task {task_id}...")
        
        # Check status to confirm completion
        status_result = check_generation_status(task_id)
        if not status_result or status_result.get("status") != "success":
            print("ERROR: Task not completed")
            return None
            
        # Get WAV URL
        wav_url = status_result.get("audioUrl")
        
        if wav_url:
            print(f"WAV URL: {wav_url}")
            return wav_url
        else:
            print("No WAV URL in response")
            return None
            
    except Exception as e:
        print(f"Error getting WAV format: {str(e)}")
        return None

def generate_mp4_video(task_id, audio_id=None, author="AI Music Creator", domain_name=None):
    """
    Function to generate MP4 video using Suno API
    
    Args:
        task_id: Task ID
        audio_id: Audio ID (if not specified, get from task ID)
        author: Author name
        domain_name: Domain name
        
    Returns:
        URL of generated MP4 video
    """
    try:
        print(f"\nGenerating MP4 video for task {task_id}...")
        
        # Check API key
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return {"error": "SUNO_API_KEY is not set in environment variables"}
        
        # If audio_id not specified, check status from task ID to get it
        if not audio_id:
            status_result = check_generation_status(task_id)
            if not status_result or status_result.get("status") != "success":
                print("ERROR: Task not completed or audio_id not available")
                return {"error": "Task not completed or audio_id not available"}
                
            # Get audio ID (depends on API response format)
            if "data" in status_result and isinstance(status_result["data"], list) and len(status_result["data"]) > 0:
                audio_id = status_result["data"][0].get("id")
            
            if not audio_id:
                print("ERROR: Could not find audio_id in task status")
                return {"error": "Could not find audio_id in task status"}
        
        # Set callback URL
        callback_url = os.getenv("CALLBACK_URL")
        if not callback_url:
            print("WARNING: CALLBACK_URL is not set")
            callback_url = "http://localhost:5001/callback"
        
        # Use default value if domain name not specified
        if not domain_name:
            domain_name = "https://vaibes.fun/"
        
        # Prepare request data
        data = {
            "taskId": task_id,
            "audioId": audio_id,
            "callBackUrl": callback_url,
            "author": author,
            "domainName": domain_name
        }
        
        print(f"MP4 generation request data: {json.dumps(data, ensure_ascii=False)}")
        
        # Call MP4 generation API
        result = call_suno_api("/api/v1/mp4/generate", data)
        
        # Process response
        response_data = result.get("data", {})
        
        # Process successful response
        if result.get("code") == 200:
            print(f"MP4 generation request submitted successfully")
            
            # Get MP4 URL from response
            mp4_url = response_data.get("videoUrl")
            
            if mp4_url:
                print(f"MP4 URL: {mp4_url}")
                return {
                    "success": True,
                    "task_id": task_id,
                    "audio_id": audio_id,
                    "mp4_url": mp4_url
                }
            else:
                # If no MP4 URL, return task ID for later status check
                print("MP4 URL not available yet, check status later")
                return {
                    "success": True,
                    "status": "pending",
                    "task_id": task_id,
                    "audio_id": audio_id,
                    "message": "MP4 generation request submitted, check status later"
                }
        else:
            error_msg = f"MP4 generation failed: {result.get('msg')}"
            print(f"ERROR: {error_msg}")
            return {"error": error_msg}
            
    except Exception as e:
        print(f"Error generating MP4 video: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

def generate_lyrics(prompt):
    """
    Function to generate lyrics using Suno API
    
    Args:
        prompt: Lyrics generation prompt
        
    Returns:
        Generated lyrics
    """
    try:
        print(f"\nGenerating lyrics with Suno API...")
        print(f"Prompt: '{prompt}'")
        
        # Check API key
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return None
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Prepare request data
        data = {
            "prompt": prompt,
            "taskId": task_id
        }
        
        # Call lyrics generation API
        result = call_suno_api("/api/v1/lyrics", data)
        
        # Get lyrics from response
        response_data = result.get("data", {})
        lyrics = response_data.get("lyrics")
        
        if not lyrics:
            print("ERROR: No lyrics in response")
            return None
            
        print(f"Lyrics generation successful!")
        print(f"Lyrics: {lyrics}")
        
        return lyrics
        
    except Exception as e:
        print(f"Error generating lyrics: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def download_file(url, filename=None, output_dir=None):
    """
    Function to download file from URL
    
    Args:
        url: URL to download
        filename: Filename to save (auto-generated if not specified)
        output_dir: Output directory (default if not specified)
        
    Returns:
        Local file path
    """
    try:
        if not output_dir:
            output_dir = OUTPUT_DIR
            
        if not filename:
            # Get filename from URL or use UUID
            filename = os.path.basename(url.split('?')[0]) or f"file_{uuid.uuid4()}"
        
        local_path = os.path.join(output_dir, filename)
        
        print(f"\nDownloading file from {url} to {local_path}...")
        
        # Download file
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"Download completed: {local_path}")
            return local_path
        else:
            print(f"Download failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        import traceback
        traceback.print_exc()
        return None