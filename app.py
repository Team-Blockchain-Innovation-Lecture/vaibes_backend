import os
import time
import json
import uuid
import logging
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv
from datetime import datetime
from modules.music.generator import generate_music_with_suno
from modules.video.generator import generate_video_from_text, merge_video_audio

# Initialize Flask application
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # Don't escape non-ASCII characters like Japanese
load_dotenv(dotenv_path=".env")

# Set output directory
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Default prompt
DEFAULT_PROMPT = "A calm atmosphere combining jazz and classical music"

# Dictionary to store callback data
callback_data = {}

# Dictionary to store request ID and task ID mapping
app.request_task_mapping = {}

logger = logging.getLogger(__name__)

# Root endpoint: API documentation
@app.route('/')
def api_docs():
    response_data = {
        "name": "Music Generation API",
        "version": "1.0",
        "endpoints": [
            {
                "path": "/api/generate",
                "method": "POST",
                "description": "Generate music using Suno API",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "Description text for the music (required)"
                    },
                    {
                        "name": "genre",
                        "type": "string",
                        "description": "Music genre (optional)"
                    },
                    {
                        "name": "with_lyrics",
                        "type": "boolean",
                        "description": "Whether to include lyrics (default: true)"
                    },
                    {
                        "name": "model_version",
                        "type": "string",
                        "description": "Model version to use (default: v4)"
                    }
                ]
            },
            {
                "path": "/api/generate-lyrics",
                "method": "POST",
                "description": "Generate lyrics using Suno API",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "Description text for the lyrics (required)"
                    }
                ]
            },
            {
                "path": "/api/download/<filename>",
                "method": "GET",
                "description": "Download generated files"
            },
            {
                "path": "/api/check-api-key",
                "method": "GET",
                "description": "Check Suno API key configuration"
            },
            {
                "path": "/api/test-connection",
                "method": "GET",
                "description": "Test connection to Suno API"
            },
            {
                "path": "/api/check-status",
                "method": "POST",
                "description": "Check task status"
            },
            {
                "path": "/callback",
                "method": "GET",
                "description": "Display latest callback data"
            },
            {
                "path": "/callbacks",
                "method": "GET",
                "description": "List all stored callback data"
            },
            {
                "path": "/callback/<task_id>",
                "method": "GET",
                "description": "Get callback data for a specific task ID"
            },
            {
                "path": "/simulate-callback",
                "method": "POST",
                "description": "Endpoint for simulating callbacks"
            },
            {
                "path": "/clear-callbacks",
                "method": "POST",
                "description": "Clear all stored callback data"
            },
            {
                "path": "/api/generate-mp4",
                "method": "POST",
                "description": "API endpoint for generating MP4 video"
            },
            {
                "path": "/api/check-mp4-status",
                "method": "POST",
                "description": "API endpoint for checking MP4 generation status"
            },
            {
                "path": "/api/generate-with-callback",
                "method": "POST",
                "description": "Endpoint for generating music and waiting for callback"
            },
            {
                "path": "/api/generate-mp4-with-callback",
                "method": "POST",
                "description": "API endpoint for generating MP4 video and waiting for callback"
            },
            {
                "path": "/api/generate-video",
                "method": "POST",
                "description": "Generate video from text",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "Text for video generation (required)"
                    },
                    {
                        "name": "aspect_ratio",
                        "type": "string",
                        "description": "Aspect ratio of the video (default: '9:16')"
                    },
                    {
                        "name": "duration",
                        "type": "integer",
                        "description": "Duration of the video (seconds) (default: 8)"
                    },
                    {
                        "name": "style",
                        "type": "string",
                        "description": "Style of the video (options: 'anime', '3d_animation', 'clay', 'comic', 'cyberpunk'; default: 'cyberpunk')"
                    }
                ]
            },
            {
                "path": "/api/merge-video-audio",
                "method": "POST",
                "description": "Merge video and audio",
                "parameters": [
                    {
                        "name": "video_url",
                        "type": "string",
                        "description": "Video URL (required)"
                    },
                    {
                        "name": "audio_url",
                        "type": "string",
                        "description": "Audio URL (required)"
                    },
                    {
                        "name": "video_start",
                        "type": "integer",
                        "description": "Video start position (seconds) (default: 0)"
                    },
                    {
                        "name": "video_end",
                        "type": "integer",
                        "description": "Video end position (seconds, -1 for end) (default: -1)"
                    },
                    {
                        "name": "audio_start",
                        "type": "integer",
                        "description": "Audio start position (seconds) (default: 0)"
                    },
                    {
                        "name": "audio_end",
                        "type": "integer",
                        "description": "Audio end position (seconds, -1 for end) (default: -1)"
                    },
                    {
                        "name": "audio_fade_in",
                        "type": "integer",
                        "description": "Audio fade-in time (seconds) (default: 0)"
                    },
                    {
                        "name": "audio_fade_out",
                        "type": "integer",
                        "description": "Audio fade-out time (seconds) (default: 0)"
                    },
                    {
                        "name": "override_audio",
                        "type": "boolean",
                        "description": "Whether to override existing audio (default: false)"
                    },
                    {
                        "name": "merge_intensity",
                        "type": "number",
                        "description": "Merge intensity (0.0-1.0) (default: 0.5)"
                    },
                    {
                        "name": "output_path",
                        "type": "string",
                        "description": "Output file path (default: 'result.mp4')"
                    }
                ]
            },
            {
                "path": "/api/webhook/segmind",
                "method": "POST",
                "description": "Segmind webhook endpoint",
                "parameters": [
                    {
                        "name": "event_type",
                        "type": "string",
                        "description": "Event type (NODE_RUN or GRAPH_RUN)"
                    },
                    {
                        "name": "node_id",
                        "type": "string",
                        "description": "Node ID (for NODE_RUN event)"
                    },
                    {
                        "name": "graph_id",
                        "type": "string",
                        "description": "Graph ID (for GRAPH_RUN event)"
                    },
                    {
                        "name": "status",
                        "type": "string",
                        "description": "Processing status"
                    },
                    {
                        "name": "output_url",
                        "type": "string",
                        "description": "Output URL (for NODE_RUN event)"
                    },
                    {
                        "name": "outputs",
                        "type": "object",
                        "description": "Output data (for GRAPH_RUN event)"
                    }
                ]
            }
        ],
        "default_prompt": DEFAULT_PROMPT
    }
    
    # Use ensure_ascii=False to output Japanese characters as is
    return app.response_class(
        response=json.dumps(response_data, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

# Music generation endpoint
@app.route('/api/generate', methods=['POST'])
def generate_audio():
    data = request.json
    
    try:
        prompt = data.get('prompt', '')
        genre = data.get('genre', '')
        instrumental = data.get('instrumental', False)
        model_version = data.get('model_version', 'v4')
        
        # Request music generation
        result = generate_music_with_suno(
            prompt=prompt,
            reference_style=genre,
            with_lyrics=not instrumental,
            model_version=model_version
        )
        
        if 'error' in result:
            return jsonify(result), 500
        
        # レスポンスからtaskIdを取得
        response_task_id = result.get('response_task_id')
        if not response_task_id:
            return jsonify({
                "error": "No taskId in response",
                "details": result
            }), 500
        
        # Return immediate response (changed to asynchronous processing)
        return jsonify({
            "success": True,
            "task_id": response_task_id,
            "status": "processing",
            "message": "Music generation started. Check status at /api/check-status",
            "check_status_endpoint": f"/api/check-status"
        })
        
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Lyrics generation endpoint
@app.route('/api/generate-lyrics', methods=['POST'])
def generate_lyrics_endpoint():
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        prompt = data.get('prompt', '')
        
        # Prompt validation
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
        
        print(f"Received lyrics generation request:")
        print(f"Prompt: {prompt}")
        
        # API key check
        suno_api_key = os.getenv("SUNO_API_KEY")
        if not suno_api_key:
            return jsonify({"error": "SUNO_API_KEY is not set"}), 500
        
        # Generate lyrics using Suno API
        from modules.music.generator import generate_lyrics
        
        lyrics = generate_lyrics(prompt)
        
        if not lyrics:
            return jsonify({"error": "Lyrics generation failed"}), 500
        
        # Return response
        return jsonify({
            "success": True,
            "lyrics": lyrics,
            "prompt": prompt
        })
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# API key check endpoint
@app.route('/api/check-api-key', methods=['GET'])
def check_api_key():
    try:
        suno_api_key = os.getenv("SUNO_API_KEY")
        if not suno_api_key:
            return jsonify({"error": "SUNO_API_KEY is not set"}), 500
            
        # Display only the first and last few characters of the API key for security
        masked_key = f"{suno_api_key[:5]}...{suno_api_key[-5:]}" if len(suno_api_key) > 10 else "***"
        
        return jsonify({
            "success": True,
            "message": "SUNO_API_KEY is set",
            "key_preview": masked_key,
            "key_length": len(suno_api_key)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Download endpoint
@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        error_msg = f"Download error: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

# File download endpoint (from URL)
@app.route('/api/download-from-url', methods=['POST'])
def download_from_url():
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        url = data.get('url', '')
        filename = data.get('filename', '')
        
        # URL validation
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        print(f"Received download request:")
        print(f"URL: {url}")
        print(f"Filename: {filename}")
        
        # Download file
        from modules.music.generator import download_file as download_file_func
        
        local_path = download_file_func(url, filename)
        
        if not local_path:
            return jsonify({"error": "Download failed"}), 500
        
        # Get filename
        filename = os.path.basename(local_path)
        
        # Return response
        return jsonify({
            "success": True,
            "message": "File downloaded successfully",
            "filename": filename,
            "download_url": f"/api/download/{filename}"
        })
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Status check endpoint
@app.route('/api/check-status', methods=['POST'])
def check_status():
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        task_id = data.get('task_id', '')
        
        if not task_id:
            return jsonify({"error": "Task ID is required"}), 400
            
        # Call status check module
        from modules.music.generator import check_generation_status
        
        status_result = check_generation_status(task_id)
        
        if not status_result:
            return jsonify({
                "success": False,
                "error": "Failed to check status",
                "task_id": task_id
            }), 500
        
        # Check status
        status = status_result.get("status", "unknown")
        
        # Access API response fields according to API response field names
        audio_url = status_result.get("audioUrl")
        lyrics = status_result.get("lyrics")
        cover_image_url = status_result.get("coverImageUrl")
        
        # Return response
        return jsonify({
            "success": True,
            "status": status,
            "audio_url": audio_url,
            "lyrics": lyrics,
            "cover_image_url": cover_image_url,
            "task_id": task_id,
            "message": "Music generation is still in progress." if status != "success" else "Music generation completed."
        })
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/callback', methods=['GET', 'POST'])
def callback():
    if request.method == 'GET':
        # For GET requests, display current callback data
        return jsonify({
            "status": "Callback data available" if callback_data else "No callback data available",
            "message": "Callbacks have been received" if callback_data else "No callbacks have been received yet",
            "data": callback_data
        })
    
    # For POST requests
    try:
        # Get request data
        data = request.get_json()
        if not data:
            print("Error: Invalid JSON data in callback")
            return jsonify({"error": "Invalid JSON data"}), 400
        
        print(f"★★★ Received callback data: {json.dumps(data, ensure_ascii=False)[:500]}... ★★★")
        
        # Get task ID (matching Suno's callback format)
        task_ids = set()  # Store all possible task IDs
        
        # Collect all task IDs from callback data
        def collect_task_ids(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ["task_id", "taskId"] and isinstance(v, str):
                        task_ids.add(v)
                    # Extract task ID from title field
                    if k == "title" and isinstance(v, str) and "Generated Music" in v:
                        title_task_id = v.split("Generated Music")[-1].strip()
                        if title_task_id:
                            task_ids.add(title_task_id)
                    collect_task_ids(v)
            elif isinstance(obj, list):
                for item in obj:
                    collect_task_ids(item)
        
        collect_task_ids(data)
        
        print(f"★★★ Found task IDs in callback data: {task_ids} ★★★")
        
        if not task_ids:
            print(f"Warning: No task_id found in callback data")
            # Generate temporary ID
            task_id = str(uuid.uuid4())
            task_ids.add(task_id)
            print(f"Generated temporary task_id: {task_id}")
        
        # Store callback data
        callback_time = datetime.now().isoformat()
        callback_info = {
            "data": data,
            "timestamp": callback_time
        }
        
        # Store with all found task IDs
        for task_id in task_ids:
            callback_data[task_id] = callback_info
            print(f"★★★ Stored callback data for task_id: {task_id} ★★★")
        
        print(f"★★★ Available callback keys after storing: {list(callback_data.keys())} ★★★")
        
        # Return normal response
        return jsonify({"success": True, "task_ids": list(task_ids)})
        
    except Exception as e:
        print(f"Error processing callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/callbacks', methods=['GET'])
def list_callbacks():
    """
    Endpoint to list all stored callback data
    """
    try:
        print(f"Listing all callbacks. Available keys: {list(callback_data.keys())}")
        
        if not callback_data:
            return jsonify({
                "status": "No callback data available",
                "message": "No callbacks have been received yet"
            })
        
        # Create callback data summary
        callback_summary = {}
        for task_id, data in callback_data.items():
            callback_summary[task_id] = {
                "timestamp": data.get("timestamp"),
                "status": data.get("data", {}).get("code", "unknown"),
                "message": data.get("data", {}).get("msg", "No message")
            }
        
        return jsonify({
            "status": "success",
            "message": "All callback data",
            "count": len(callback_data),
            "callbacks": callback_summary
        })
    except Exception as e:
        print(f"Error listing callbacks: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Error listing callbacks: {str(e)}"
        }), 500

@app.route('/callback/<task_id>', methods=['GET'])
def get_callback(task_id):
    """
    Endpoint to get callback data for a specific task ID
    """
    try:
        print(f"Accessing callback data for task_id: {task_id}")
        print(f"Available callback keys: {list(callback_data.keys())}")
        
        # Search for exact match
        if task_id in callback_data:
            print(f"Found exact match for task_id: {task_id}")
            return jsonify({
                "status": "success",
                "message": f"Callback data for task_id: {task_id}",
                "task_id": task_id,
                "timestamp": callback_data[task_id].get("timestamp"),
                "data": callback_data[task_id].get("data")
            })
        
        # Search for partial match (keys containing part of task_id)
        for key in callback_data.keys():
            if task_id in key or key in task_id:
                print(f"Found partial match: {key} for task_id: {task_id}")
                return jsonify({
                    "status": "success",
                    "message": f"Callback data for task_id: {task_id} (matched with {key})",
                    "task_id": key,
                    "timestamp": callback_data[key].get("timestamp"),
                    "data": callback_data[key].get("data")
                })
        
        # Recursively search in callback data
        for key, cb in callback_data.items():
            def find_task_id(obj):
                if isinstance(obj, dict):
                    # Check task_id field
                    if "task_id" in obj and obj["task_id"] == task_id:
                        return True
                    # Check title field
                    if "title" in obj and isinstance(obj["title"], str):
                        title_task_id = obj["title"].split("Generated Music")[-1].strip()
                        if title_task_id and title_task_id in task_id:
                            return True
                    for v in obj.values():
                        if find_task_id(v):
                            return True
                elif isinstance(obj, list):
                    for item in obj:
                        if find_task_id(item):
                            return True
                return False
            
            if find_task_id(cb.get("data", {})):
                print(f"Found task_id in nested data: {key}")
                return jsonify({
                    "status": "success",
                    "message": f"Callback data for task_id: {task_id} (found in {key})",
                    "task_id": key,
                    "timestamp": cb.get("timestamp"),
                    "data": cb.get("data")
                })
        
        print(f"Task ID {task_id} not found in callback_data")
        return jsonify({
            "status": "not_found",
            "message": f"No callback data found for task_id: {task_id}",
            "available_tasks": list(callback_data.keys())
        }), 404
    except Exception as e:
        print(f"Error retrieving callback data for task_id {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"Error retrieving callback data: {str(e)}"
        }), 500

@app.route('/clear-callbacks', methods=['POST'])
def clear_callbacks():
    """
    Endpoint to clear all stored callback data
    """
    try:
        callback_data.clear()
        return jsonify({
            "success": True,
            "message": "All callback data cleared"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/generate-mp4', methods=['POST'])
def api_generate_mp4():
    """
    API endpoint for generating MP4 video
    """
    try:
        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        task_id = data.get('task_id')
        audio_id = data.get('audio_id')
        author = data.get('author', 'AI Music Creator')
        domain_name = data.get('domain_name')
        
        if not task_id:
            return jsonify({"error": "task_id is required"}), 400
        
        # Call MP4 generation function
        from modules.music.generator import generate_mp4_video
        result = generate_mp4_video(task_id, audio_id, author, domain_name)
        
        if result and "error" in result:
            return jsonify(result), 400
            
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in MP4 generation API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-mp4-status', methods=['POST'])
def api_check_mp4_status():
    """
    API endpoint for checking MP4 generation status
    """
    try:
        # Get data from request
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({"error": "task_id is required"}), 400
        
        # Check callback data
        if task_id in callback_data:
            callback_info = callback_data[task_id]
            callback_data_content = callback_info.get("data", {})
            
            # Look for MP4 URL
            mp4_url = None
            
            # Search based on callback data structure
            if "data" in callback_data_content and isinstance(callback_data_content["data"], dict):
                if "data" in callback_data_content["data"] and isinstance(callback_data_content["data"]["data"], list):
                    for item in callback_data_content["data"]["data"]:
                        if "video_url" in item:
                            mp4_url = item["video_url"]
                            break
            
            if mp4_url:
                return jsonify({
                    "success": True,
                    "status": "success",
                    "task_id": task_id,
                    "mp4_url": mp4_url,
                    "timestamp": callback_info.get("timestamp")
                })
        
        # If no callback data, check status via API
        from modules.music.generator import check_generation_status
        status_result = check_generation_status(task_id)
        
        if not status_result:
            return jsonify({
                "success": False,
                "status": "unknown",
                "task_id": task_id,
                "message": "Could not retrieve status"
            }), 404
            
        # Look for MP4 URL
        mp4_url = status_result.get("videoUrl")
        
        if mp4_url:
            return jsonify({
                "success": True,
                "status": "success",
                "task_id": task_id,
                "mp4_url": mp4_url
            })
        else:
            return jsonify({
                "success": True,
                "status": "pending",
                "task_id": task_id,
                "message": "MP4 is still being generated"
            })
        
    except Exception as e:
        print(f"Error in MP4 status check API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-with-callback', methods=['POST'])
def generate_audio_with_callback():
    data = request.json
    
    try:
        prompt = data.get('prompt', '')
        genre = data.get('genre', '')
        instrumental = data.get('instrumental', False)
        model_version = data.get('model_version', 'v4')
        timeout = data.get('timeout', 3)  # Timeout extended to 3 seconds
        request_id = data.get('request_id', str(uuid.uuid4()))  # Request ID for identification (sent from client or auto-generated)
        
        print(f"★★★ Received generate request with request_id: {request_id} ★★★")
        
        # Request music generation
        result = generate_music_with_suno(
            prompt=prompt,
            reference_style=genre,
            with_lyrics=not instrumental,
            model_version=model_version
        )
        
        if 'error' in result:
            return jsonify(result), 500
            
        # Get task ID
        task_id = result.get('task_id')
        print(f"★★★ Task ID: {task_id} for request_id: {request_id}, waiting for callback... ★★★")
        
        # Store request ID and task ID mapping for future extension
        request_task_mapping = getattr(app, 'request_task_mapping', {})
        request_task_mapping[request_id] = task_id
        app.request_task_mapping = request_task_mapping
        
        # Function to monitor callback data keys (for cases where task_id format is different)
        def find_matching_callback():
            # Exact match
            if task_id in callback_data:
                print(f"★★★ Found exact match callback for task_id: {task_id}, request_id: {request_id} ★★★")
                return callback_data[task_id]
            
            # Partial match (search for keys containing part of task_id)
            for key in callback_data.keys():
                if task_id in key or key in task_id:
                    print(f"★★★ Found callback with partial match: {key} for request_id: {request_id} ★★★")
                    return callback_data[key]
                    
            # Search in JSON of callback data
            for key, cb in callback_data.items():
                cb_data = cb.get("data", {})
                if isinstance(cb_data, dict):
                    # Check data_obj for task_id
                    data_obj = cb_data.get("data", {})
                    if isinstance(data_obj, dict) and data_obj.get("task_id") == task_id:
                        print(f"★★★ Found task_id in nested data: {key} for request_id: {request_id} ★★★")
                        return cb
                        
            return None
            
        # Check if callback has already arrived (already processed)
        cb_data = find_matching_callback()
        if cb_data:
            print(f"★★★ Callback already received for task {task_id}, request_id: {request_id} - returning immediately ★★★")
            return jsonify({
                "success": True,
                "task_id": task_id,
                "request_id": request_id,
                "status": "completed",
                "callback_data": cb_data,
                "matched_callback_id": task_id,
                "message": "Music generation completed (callback already received)"
            })
        
        # Wait for callback
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Search for matching callback
            cb_data = find_matching_callback()
            if cb_data:
                print(f"★★★ Callback found for task {task_id}, request_id: {request_id} - returning immediately without waiting for timeout ★★★")
                
                # Return callback data immediately (without waiting for timeout)
                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "request_id": request_id,
                    "status": "completed",
                    "callback_data": cb_data,
                    "matched_callback_id": task_id,
                    "message": "Music generation completed"
                })
            
            # Check status (skip if error occurs)
            try:
                from modules.music.generator import check_generation_status
                status_result = check_generation_status(task_id)
                
                if status_result and status_result.get("status") == "success":
                    print(f"★★★ Task {task_id}, request_id: {request_id} completed successfully (via status check) - returning immediately without waiting for timeout ★★★")
                    return jsonify({
                        "success": True,
                        "task_id": task_id,
                        "request_id": request_id,
                        "status": "completed",
                        "result": status_result,
                        "message": "Music generation completed"
                    })
            except Exception as status_error:
                print(f"Status check error (non-fatal) for request_id: {request_id}: {str(status_error)}")
            
            # Wait for a while
            time.sleep(2)
            
            # Check if callback data exists (this check is done every time)
            print(f"Waiting for callback, request_id: {request_id}, elapsed time: {int(time.time() - start_time)}s, available keys: {list(callback_data.keys())}")
        
        # If timeout reached, return available callback data if any
        print(f"Timeout reached for request_id: {request_id}. Looking for any available callback data.")
        for key, value in callback_data.items():
            # Check callback data creation time
            callback_time = datetime.fromisoformat(value.get("timestamp", ""))
            request_time = datetime.fromtimestamp(start_time)
            
            # Search for callback data created after request
            if callback_time > request_time:
                print(f"Found callback data created after request: {key} for request_id: {request_id}")
                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "request_id": request_id,
                    "matched_callback_id": key,
                    "status": "completed",
                    "callback_data": value,
                    "message": "Music generation completed (callback found after timeout)"
                })
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "request_id": request_id,
            "status": "processing",
            "message": f"Timeout reached. Processing is ongoing. Check status at /api/check-status"
        })
        
    except Exception as e:
        print(f"Error generating audio with callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-mp4-with-callback', methods=['POST'])
def api_generate_mp4_with_callback():
    """
    MP4 video is generated and waiting for callback API endpoint
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "無効なJSONデータ"}), 400
            
        task_id = data.get('task_id')
        audio_id = data.get('audio_id')
        author = data.get('author', 'AI Music Creator')
        domain_name = data.get('domain_name')
        timeout = data.get('timeout', 180)  # Timeout extended to 3 minutes
        request_id = data.get('request_id', str(uuid.uuid4()))  # Request ID for identification
        
        print(f"★★★ Received MP4 generate request with request_id: {request_id} ★★★")
        
        if not task_id:
            return jsonify({"error": "task_idは必須です"}), 400
            
        # If audio_id is not specified, check task_id callback data
        if not audio_id:
            # Check task_id callback data
            if task_id in callback_data:
                cb_data = callback_data[task_id].get("data", {})
                if "data" in cb_data and "data" in cb_data["data"]:
                    music_items = cb_data["data"]["data"]
                    if isinstance(music_items, list) and len(music_items) > 0:
                        # Use first music item ID
                        audio_id = music_items[0].get("id")
                        print(f"Using first audio ID from callback data: {audio_id} for request_id: {request_id}")
        
        if not audio_id:
            return jsonify({"error": "audio_idが指定されておらず、コールバックデータからも取得できませんでした"}), 400
            
        # Clear existing MP4 callback data (to prevent duplication)
        mp4_callbacks_to_remove = []
        for key in callback_data.keys():
            cb_data = callback_data[key].get("data", {})
            if "mp4_request_time" in cb_data and cb_data.get("original_task_id") == task_id and cb_data.get("audio_id") == audio_id:
                mp4_callbacks_to_remove.append(key)
                
        for key in mp4_callbacks_to_remove:
            print(f"Removing old MP4 callback: {key} for request_id: {request_id}")
            del callback_data[key]
        
        # Record MP4 request time
        mp4_request_time = datetime.now().isoformat()
        
        # Record current callback_data keys (for detecting new callback)
        callback_data_keys_before = set(callback_data.keys())
        
        # Call MP4 generation function
        from modules.music.generator import generate_mp4_video
        result = generate_mp4_video(task_id, audio_id, author, domain_name)
        
        if result and "error" in result:
            return jsonify(result), 400
            
        # MP4 generation task ID
        mp4_task_id = result.get("task_id")
        print(f"★★★ MP4 Task ID: {mp4_task_id} for request_id: {request_id}, waiting for callback... ★★★")
        
        # Store request ID and task ID mapping
        request_task_mapping = getattr(app, 'request_task_mapping', {})
        request_task_mapping[request_id] = mp4_task_id
        app.request_task_mapping = request_task_mapping
        
        # Store MP4 request information globally (for callback matching)
        mp4_request_info = {
            "mp4_task_id": mp4_task_id,
            "original_task_id": task_id,
            "audio_id": audio_id,
            "request_id": request_id,
            "request_time": mp4_request_time
        }
        
        # Function to identify MP4 callback
        def find_mp4_callback():
            # Exact match (MP4 task ID)
            if mp4_task_id in callback_data:
                cb_data = callback_data[mp4_task_id]
                # Check: Whether video_url exists in callback data
                raw_data = cb_data.get("data", {})
                if "data" in raw_data and "video_url" in raw_data.get("data", {}):
                    print(f"★★★ Found MP4 callback by task_id: {mp4_task_id} for request_id: {request_id} ★★★")
                    return cb_data
            
            # Search in callback data
            for key, cb in callback_data.items():
                if key == task_id:
                    # Original task ID is more likely to be music data, so skip
                    continue
                    
                # Check if new callback is added after request
                if key not in callback_data_keys_before:
                    print(f"Checking new callback: {key} for request_id: {request_id}")
                    
                    cb_data = cb.get("data", {})
                    
                    # MP4 callback feature: video_url key exists
                    if "data" in cb_data and ("video_url" in cb_data.get("data", {}) or "stream_video_url" in cb_data.get("data", {})):
                        print(f"★★★ Found MP4 callback with video URL in new callback: {key} for request_id: {request_id} ★★★")
                        return cb
                    
                    # Check for video-related string in data keys or values
                    if isinstance(cb_data, dict):
                        data_found = False
                        for k, v in cb_data.items():
                            if isinstance(v, str) and (".mp4" in v.lower() or "video" in v.lower()):
                                print(f"★★★ Found MP4 URL in callback data: {key}, value: {v[:30]}... for request_id: {request_id} ★★★")
                                data_found = True
                                break
                        if data_found:
                            return cb
                        
            return None
        
        # Check if callback has already arrived
        cb_data = find_mp4_callback()
        if cb_data:
            print(f"★★★ MP4 callback already received for request_id: {request_id} - returning immediately ★★★")
            
            # Return callback data as it is (only data content)
            raw_callback_data = cb_data.get("data", {})
            
            # If streaming URL is not included, add
            if "data" in raw_callback_data and "video_url" in raw_callback_data["data"]:
                video_url = raw_callback_data["data"]["video_url"]
                
                # If streaming URL is not available, generate from usual URL
                if "stream_video_url" not in raw_callback_data["data"]:
                    # Convert URL to streaming URL
                    stream_url = video_url
                    if ".mp4" in video_url:
                        stream_url = video_url.replace(".mp4", "_stream.mp4")
                    
                    # Add streaming URL
                    raw_callback_data["data"]["stream_video_url"] = stream_url
                    print(f"Added stream_video_url: {stream_url} for request_id: {request_id}")
            
            # Add request ID
            if "data" in raw_callback_data:
                raw_callback_data["data"]["request_id"] = request_id
            
            # Return directly callback data content as it is
            return jsonify(raw_callback_data)
            
        # Wait for MP4 task ID related callback
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Search MP4 callback
            cb_data = find_mp4_callback()
            if cb_data:
                print(f"★★★ MP4 callback found for request_id: {request_id}, returning data ★★★")
                
                # Return callback data as it is (only data content)
                raw_callback_data = cb_data.get("data", {})
                
                # If streaming URL is not included, add
                if "data" in raw_callback_data and "video_url" in raw_callback_data["data"]:
                    video_url = raw_callback_data["data"]["video_url"]
                    
                    # If streaming URL is not available, generate from usual URL
                    if "stream_video_url" not in raw_callback_data["data"]:
                        # Convert URL to streaming URL
                        # Example: example.com/file.mp4 → example.com/stream/file.mp4
                        stream_url = video_url
                        if ".mp4" in video_url:
                            stream_url = video_url.replace(".mp4", "_stream.mp4")
                        
                        # Add streaming URL
                        raw_callback_data["data"]["stream_video_url"] = stream_url
                        print(f"Added stream_video_url: {stream_url} for request_id: {request_id}")
                
                # Add request ID
                if "data" in raw_callback_data:
                    raw_callback_data["data"]["request_id"] = request_id
                
                # Return directly callback data content as it is
                return jsonify(raw_callback_data)
            
            # Check MP4 URL
            try:
                # Call status check API
                from modules.music.generator import check_generation_status
                status_result = check_generation_status(task_id)
                
                if status_result:
                    # Search MP4 URL
                    mp4_url = status_result.get("videoUrl")
                    
                    if mp4_url:
                        print(f"★★★ MP4 URL found via status check: {mp4_url} for request_id: {request_id} ★★★")
                        
                        # Generate streaming URL
                        stream_url = mp4_url
                        if ".mp4" in mp4_url:
                            stream_url = mp4_url.replace(".mp4", "_stream.mp4")
                        
                        # Return callback data in exactly the same format as callback data
                        return jsonify({
                            "code": 200,
                            "data": {
                                "task_id": mp4_task_id,
                                "request_id": request_id,
                                "video_url": mp4_url,
                                "stream_video_url": stream_url
                            },
                            "msg": "All generated successfully."
                        })
            except Exception as status_error:
                print(f"MP4 status check error (non-fatal) for request_id: {request_id}: {str(status_error)}")
            
            # Wait for a while
            time.sleep(2)
            
            # Progress display
            print(f"Waiting for MP4 callback, request_id: {request_id}, elapsed time: {int(time.time() - start_time)}s, available keys: {list(callback_data.keys())}")
            # Periodically output new callback data for debugging
            if int(time.time() - start_time) % 20 < 2:  # Output every 20 seconds
                for key in callback_data.keys():
                    if key not in callback_data_keys_before:
                        print(f"New callback data found for key {key} for request_id: {request_id}: {json.dumps(callback_data[key].get('data', {}), ensure_ascii=False)[:200]}...")
        
        # If timeout reached
        return jsonify({
            "code": 408,
            "data": {
                "task_id": mp4_task_id,
                "request_id": request_id,
                "status": "processing"
            },
            "msg": f"MP4 generation timed out (request_id: {request_id}). Processing is ongoing."
        })
        
    except Exception as e:
        print(f"MP4 generation API error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "data": None,
            "msg": f"Error occurred: {str(e)}"
        }), 500

@app.route('/api/generate-video', methods=['POST'])
async def generate_video():
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # Get parameters (optional ones are set to default values)
        prompt = data.get('prompt')+", \nThe text above is the lyrics to the song. Generate a video to match the lyrics. Moreover, turn it into an explosively viral, hilarious meme video for social media."
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
            
        aspect_ratio = data.get('aspect_ratio', '9:16')
        duration = data.get('duration', 8)
        style = data.get('style', 'cyberpunk')
        
        # リクエストパラメータをコンソールに出力
        print(f"🎬 Received video generation API request:")
        print(f"🎬 Style: {style}")
        print(f"🎬 Prompt: {prompt}")
        print(f"🎬 Aspect ratio: {aspect_ratio}, Duration: {duration}s")
        # Execute video generation
        from modules.video.generator import generate_video_from_text
        result = await generate_video_from_text(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration=duration,
            style=style
        )
        
        # Return success response
        return jsonify(result)
        
    except Exception as e:
        print(f"Error generating video: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/merge-video-audio', methods=['POST'])
def merge_video_audio_endpoint():

    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # Check required parameters
        video_url = data.get('video_url')
        audio_url = data.get('audio_url')
        
        if not video_url or not audio_url:
            return jsonify({"error": "video_url and audio_url are required"}), 400
        
        # Merge video and audio
        result = merge_video_audio(
            video_url=video_url,
            audio_url=audio_url
        )
        
        if not result.get('success'):
            return jsonify(result), 500
        
        # Return success response
        return jsonify(result)
        
    except Exception as e:
        print(f"Error merging video and audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "message": "Failed to merge video and audio"
        }), 500

@app.route('/api/webhook/segmind', methods=['POST'])
def segmind_webhook():
    try:
        # Get Webhook data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        print(f"Received Segmind webhook: {json.dumps(data, ensure_ascii=False)}")
        
        # Check event type
        event_type = data.get('event_type')
        if not event_type:
            return jsonify({"error": "event_type is required"}), 400
        
        # Process based on event type
        if event_type == 'NODE_RUN':
            # Process node execution event
            node_id = data.get('node_id')
            status = data.get('status')
            output_url = data.get('output_url')
            
            print(f"Node {node_id} status: {status}")
            if output_url:
                print(f"Output URL: {output_url}")
            
            # Process necessary processing here
            # Example: Save output URL, execute next processing, etc.
            
        elif event_type == 'GRAPH_RUN':
            # Process workflow completion event
            graph_id = data.get('graph_id')
            status = data.get('status')
            outputs = data.get('outputs', {})
            
            print(f"Graph {graph_id} completed with status: {status}")
            print(f"Outputs: {json.dumps(outputs, ensure_ascii=False)}")
            
            # Process necessary processing here
            # Example: Save final result, send notification, etc.
        
        # Return success response
        return jsonify({
            "success": True,
            "message": "Webhook received and processed successfully"
        })
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "message": "Failed to process webhook"
        }), 500

if __name__ == '__main__':
    # Get port number from environment variable (default: 5001)
    port = int(os.environ.get("PORT", 5001))
    
    print(f"Starting server at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)