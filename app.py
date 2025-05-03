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

# Flaskアプリケーションの初期化
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 日本語などの非ASCII文字をエスケープしない
load_dotenv(dotenv_path=".env")

# 出力ディレクトリの設定
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# デフォルトのプロンプト
DEFAULT_PROMPT = "ジャズとクラシックが融合した落ち着いた雰囲気の曲"

# コールバックデータを保存するためのディクショナリ
callback_data = {}

# リクエストIDとタスクIDのマッピングを保存するためのディクショナリ
app.request_task_mapping = {}

logger = logging.getLogger(__name__)

# ルートエンドポイント: APIドキュメント
@app.route('/')
def api_docs():
    response_data = {
        "name": "音楽生成API",
        "version": "1.0",
        "endpoints": [
            {
                "path": "/api/generate",
                "method": "POST",
                "description": "Suno APIを使用して音楽を生成",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "音楽の説明テキスト（必須）"
                    },
                    {
                        "name": "genre",
                        "type": "string",
                        "description": "音楽のジャンル（オプション）"
                    },
                    {
                        "name": "with_lyrics",
                        "type": "boolean",
                        "description": "歌詞を含めるかどうか（デフォルト: true）"
                    },
                    {
                        "name": "model_version",
                        "type": "string",
                        "description": "使用するモデルバージョン（デフォルト: v4）"
                    }
                ]
            },
            {
                "path": "/api/generate-lyrics",
                "method": "POST",
                "description": "Suno APIを使用して歌詞を生成",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "歌詞の説明テキスト（必須）"
                    }
                ]
            },
            {
                "path": "/api/download/<filename>",
                "method": "GET",
                "description": "生成されたファイルをダウンロード"
            },
            {
                "path": "/api/check-api-key",
                "method": "GET",
                "description": "Suno APIキーの設定を確認"
            },
            {
                "path": "/api/test-connection",
                "method": "GET",
                "description": "Suno APIへの接続をテスト"
            },
            {
                "path": "/api/check-status",
                "method": "POST",
                "description": "タスクの状態を確認"
            },
            {
                "path": "/callback",
                "method": "GET",
                "description": "最新のコールバックデータを表示"
            },
            {
                "path": "/callbacks",
                "method": "GET",
                "description": "保存されているすべてのコールバックデータを一覧表示"
            },
            {
                "path": "/callback/<task_id>",
                "method": "GET",
                "description": "特定のタスクIDに対するコールバックデータを取得"
            },
            {
                "path": "/simulate-callback",
                "method": "POST",
                "description": "コールバックをシミュレートするためのエンドポイント"
            },
            {
                "path": "/clear-callbacks",
                "method": "POST",
                "description": "保存されているすべてのコールバックデータをクリアするエンドポイント"
            },
            {
                "path": "/api/generate-mp4",
                "method": "POST",
                "description": "MP4ビデオを生成するAPIエンドポイント"
            },
            {
                "path": "/api/check-mp4-status",
                "method": "POST",
                "description": "MP4生成の状態を確認するAPIエンドポイント"
            },
            {
                "path": "/api/generate-with-callback",
                "method": "POST",
                "description": "音楽を生成し、コールバックを待つエンドポイント"
            },
            {
                "path": "/api/generate-mp4-with-callback",
                "method": "POST",
                "description": "MP4ビデオを生成し、コールバックを待機するAPIエンドポイント"
            },
            {
                "path": "/api/generate-video",
                "method": "POST",
                "description": "テキストから動画を生成",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "動画生成用のテキストプロンプト（必須）"
                    },
                    {
                        "name": "aspect_ratio",
                        "type": "string",
                        "description": "アスペクト比（デフォルト: '9:16'）"
                    },
                    {
                        "name": "duration",
                        "type": "integer",
                        "description": "動画の長さ（秒）（デフォルト: 8）"
                    },
                    {
                        "name": "style",
                        "type": "string",
                        "description": "動画のスタイル（デフォルト: 'cyberpunk'）"
                    }
                ]
            },
            {
                "path": "/api/merge-video-audio",
                "method": "POST",
                "description": "動画と音声をマージ",
                "parameters": [
                    {
                        "name": "video_url",
                        "type": "string",
                        "description": "動画のURL（必須）"
                    },
                    {
                        "name": "audio_url",
                        "type": "string",
                        "description": "音声のURL（必須）"
                    },
                    {
                        "name": "video_start",
                        "type": "integer",
                        "description": "動画の開始位置（秒）（デフォルト: 0）"
                    },
                    {
                        "name": "video_end",
                        "type": "integer",
                        "description": "動画の終了位置（秒、-1は最後まで）（デフォルト: -1）"
                    },
                    {
                        "name": "audio_start",
                        "type": "integer",
                        "description": "音声の開始位置（秒）（デフォルト: 0）"
                    },
                    {
                        "name": "audio_end",
                        "type": "integer",
                        "description": "音声の終了位置（秒、-1は最後まで）（デフォルト: -1）"
                    },
                    {
                        "name": "audio_fade_in",
                        "type": "integer",
                        "description": "音声のフェードイン時間（秒）（デフォルト: 0）"
                    },
                    {
                        "name": "audio_fade_out",
                        "type": "integer",
                        "description": "音声のフェードアウト時間（秒）（デフォルト: 0）"
                    },
                    {
                        "name": "override_audio",
                        "type": "boolean",
                        "description": "既存の音声を上書きするかどうか（デフォルト: false）"
                    },
                    {
                        "name": "merge_intensity",
                        "type": "number",
                        "description": "マージの強度（0.0-1.0）（デフォルト: 0.5）"
                    },
                    {
                        "name": "output_path",
                        "type": "string",
                        "description": "出力ファイルのパス（デフォルト: 'result.mp4'）"
                    }
                ]
            },
            {
                "path": "/api/webhook/segmind",
                "method": "POST",
                "description": "SegmindのWebhookを受け取るエンドポイント",
                "parameters": [
                    {
                        "name": "event_type",
                        "type": "string",
                        "description": "イベントタイプ（NODE_RUN または GRAPH_RUN）"
                    },
                    {
                        "name": "node_id",
                        "type": "string",
                        "description": "ノードID（NODE_RUNイベントの場合）"
                    },
                    {
                        "name": "graph_id",
                        "type": "string",
                        "description": "グラフID（GRAPH_RUNイベントの場合）"
                    },
                    {
                        "name": "status",
                        "type": "string",
                        "description": "処理の状態"
                    },
                    {
                        "name": "output_url",
                        "type": "string",
                        "description": "出力URL（NODE_RUNイベントの場合）"
                    },
                    {
                        "name": "outputs",
                        "type": "object",
                        "description": "出力データ（GRAPH_RUNイベントの場合）"
                    }
                ]
            }
        ],
        "default_prompt": DEFAULT_PROMPT
    }
    
    # ensure_ascii=Falseを使用して日本語をそのまま出力
    return app.response_class(
        response=json.dumps(response_data, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

# 音楽生成エンドポイント
@app.route('/api/generate', methods=['POST'])
def generate_audio():
    data = request.json
    
    try:
        prompt = data.get('prompt', '')
        genre = data.get('genre', '')
        instrumental = data.get('instrumental', False)
        model_version = data.get('model_version', 'v4')
        
        # 音楽生成をリクエスト
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
        
        # 即時レスポンスを返す（非同期処理に変更）
        return jsonify({
            "success": True,
            "task_id": response_task_id,
            "status": "processing",
            "message": "音楽生成を開始しました。状態は /api/check-status で確認できます。",
            "check_status_endpoint": f"/api/check-status"
        })
        
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 歌詞生成エンドポイント
@app.route('/api/generate-lyrics', methods=['POST'])
def generate_lyrics_endpoint():
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        prompt = data.get('prompt', '')
        
        # プロンプトの検証
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
        
        print(f"Received lyrics generation request:")
        print(f"Prompt: {prompt}")
        
        # APIキーの確認
        suno_api_key = os.getenv("SUNO_API_KEY")
        if not suno_api_key:
            return jsonify({"error": "SUNO_API_KEY is not set"}), 500
        
        # Suno APIを使用して歌詞を生成
        from modules.music.generator import generate_lyrics
        
        lyrics = generate_lyrics(prompt)
        
        if not lyrics:
            return jsonify({"error": "Lyrics generation failed"}), 500
        
        # レスポンスを返す
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

# APIキー確認エンドポイント
@app.route('/api/check-api-key', methods=['GET'])
def check_api_key():
    try:
        suno_api_key = os.getenv("SUNO_API_KEY")
        if not suno_api_key:
            return jsonify({"error": "SUNO_API_KEY is not set"}), 500
            
        # APIキーの最初と最後の数文字だけを表示（セキュリティのため）
        masked_key = f"{suno_api_key[:5]}...{suno_api_key[-5:]}" if len(suno_api_key) > 10 else "***"
        
        return jsonify({
            "success": True,
            "message": "SUNO_API_KEY is set",
            "key_preview": masked_key,
            "key_length": len(suno_api_key)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ダウンロードエンドポイント
@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "ファイルが見つかりません"}), 404
    except Exception as e:
        error_msg = f"ダウンロードエラー: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

# ファイルダウンロードエンドポイント（URLから）
@app.route('/api/download-from-url', methods=['POST'])
def download_from_url():
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        url = data.get('url', '')
        filename = data.get('filename', '')
        
        # URLの検証
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        print(f"Received download request:")
        print(f"URL: {url}")
        print(f"Filename: {filename}")
        
        # ファイルをダウンロード
        from modules.music.generator import download_file as download_file_func
        
        local_path = download_file_func(url, filename)
        
        if not local_path:
            return jsonify({"error": "Download failed"}), 500
        
        # ファイル名を取得
        filename = os.path.basename(local_path)
        
        # レスポンスを返す
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

# 状態確認エンドポイント
@app.route('/api/check-status', methods=['POST'])
def check_status():
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        task_id = data.get('task_id', '')
        
        if not task_id:
            return jsonify({"error": "Task ID is required"}), 400
            
        # 状態確認モジュールを呼び出す
        from modules.music.generator import check_generation_status
        
        status_result = check_generation_status(task_id)
        
        if not status_result:
            return jsonify({
                "success": False,
                "error": "Failed to check status",
                "task_id": task_id
            }), 500
        
        # 状態を確認
        status = status_result.get("status", "unknown")
        
        # APIレスポンスのフィールド名に合わせてアクセス
        audio_url = status_result.get("audioUrl")
        lyrics = status_result.get("lyrics")
        cover_image_url = status_result.get("coverImageUrl")
        
        # レスポンスを返す
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
        # GETリクエストの場合、現在のコールバックデータを表示
        return jsonify({
            "status": "Callback data available" if callback_data else "No callback data available",
            "message": "Callbacks have been received" if callback_data else "No callbacks have been received yet",
            "data": callback_data
        })
    
    # POSTリクエストの場合
    try:
        # リクエストデータを取得
        data = request.get_json()
        if not data:
            print("Error: Invalid JSON data in callback")
            return jsonify({"error": "Invalid JSON data"}), 400
        
        print(f"★★★ Received callback data: {json.dumps(data, ensure_ascii=False)[:500]}... ★★★")
        
        # タスクIDを取得（Sunoのコールバック形式に合わせる）
        task_ids = set()  # すべての可能性のあるタスクIDを保存
        
        # コールバックデータ内のすべてのタスクIDを収集
        def collect_task_ids(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ["task_id", "taskId"] and isinstance(v, str):
                        task_ids.add(v)
                    # titleフィールドからタスクIDを抽出
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
            # 一時的なIDを生成
            task_id = str(uuid.uuid4())
            task_ids.add(task_id)
            print(f"Generated temporary task_id: {task_id}")
        
        # コールバックデータを保存
        callback_time = datetime.now().isoformat()
        callback_info = {
            "data": data,
            "timestamp": callback_time
        }
        
        # 見つかったすべてのタスクIDで保存
        for task_id in task_ids:
            callback_data[task_id] = callback_info
            print(f"★★★ Stored callback data for task_id: {task_id} ★★★")
        
        print(f"★★★ Available callback keys after storing: {list(callback_data.keys())} ★★★")
        
        # 通常のレスポンスを返す
        return jsonify({"success": True, "task_ids": list(task_ids)})
        
    except Exception as e:
        print(f"Error processing callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/callbacks', methods=['GET'])
def list_callbacks():
    """
    保存されているすべてのコールバックデータを一覧表示するエンドポイント
    """
    try:
        print(f"Listing all callbacks. Available keys: {list(callback_data.keys())}")
        
        if not callback_data:
            return jsonify({
                "status": "No callback data available",
                "message": "No callbacks have been received yet"
            })
        
        # コールバックデータの概要を作成
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
    特定のタスクIDに対するコールバックデータを取得するエンドポイント
    """
    try:
        print(f"Accessing callback data for task_id: {task_id}")
        print(f"Available callback keys: {list(callback_data.keys())}")
        
        # 完全一致で検索
        if task_id in callback_data:
            print(f"Found exact match for task_id: {task_id}")
            return jsonify({
                "status": "success",
                "message": f"Callback data for task_id: {task_id}",
                "task_id": task_id,
                "timestamp": callback_data[task_id].get("timestamp"),
                "data": callback_data[task_id].get("data")
            })
        
        # 部分一致で検索（タスクIDの一部が含まれるキーを探す）
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
        
        # コールバックデータ内を再帰的に検索
        for key, cb in callback_data.items():
            def find_task_id(obj):
                if isinstance(obj, dict):
                    # task_idフィールドのチェック
                    if "task_id" in obj and obj["task_id"] == task_id:
                        return True
                    # titleフィールドのチェック
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
    すべてのコールバックデータをクリアするエンドポイント
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
    MP4ビデオを生成するAPIエンドポイント
    """
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "無効なJSONデータ"}), 400
            
        task_id = data.get('task_id')
        audio_id = data.get('audio_id')
        author = data.get('author', 'AI Music Creator')
        domain_name = data.get('domain_name')
        
        if not task_id:
            return jsonify({"error": "task_idは必須です"}), 400
        
        # MP4生成関数を呼び出す
        from modules.music.generator import generate_mp4_video
        result = generate_mp4_video(task_id, audio_id, author, domain_name)
        
        if result and "error" in result:
            return jsonify(result), 400
            
        return jsonify(result)
        
    except Exception as e:
        print(f"MP4生成APIでエラーが発生: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-mp4-status', methods=['POST'])
def api_check_mp4_status():
    """
    MP4生成の状態を確認するAPIエンドポイント
    """
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "無効なJSONデータ"}), 400
            
        task_id = data.get('task_id')
        
        if not task_id:
            return jsonify({"error": "task_idは必須です"}), 400
        
        # コールバックデータを確認
        if task_id in callback_data:
            callback_info = callback_data[task_id]
            callback_data_content = callback_info.get("data", {})
            
            # MP4 URLを探す
            mp4_url = None
            
            # コールバックデータの構造に基づいて探索
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
        
        # コールバックデータがない場合は、APIで状態を確認
        from modules.music.generator import check_generation_status
        status_result = check_generation_status(task_id)
        
        if not status_result:
            return jsonify({
                "success": False,
                "status": "unknown",
                "task_id": task_id,
                "message": "状態を取得できませんでした"
            }), 404
            
        # MP4 URLを探す
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
                "message": "MP4はまだ生成中です"
            })
        
    except Exception as e:
        print(f"MP4状態確認APIでエラーが発生: {str(e)}")
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
        timeout = data.get('timeout', 3)  # タイムアウトを3秒に延長
        request_id = data.get('request_id', str(uuid.uuid4()))  # リクエスト識別用ID（クライアントから送信されるか、自動生成）
        
        print(f"★★★ Received generate request with request_id: {request_id} ★★★")
        
        # 音楽生成をリクエスト
        result = generate_music_with_suno(
            prompt=prompt,
            reference_style=genre,
            with_lyrics=not instrumental,
            model_version=model_version
        )
        
        if 'error' in result:
            return jsonify(result), 500
            
        # タスクIDを取得
        task_id = result.get('task_id')
        print(f"★★★ Task ID: {task_id} for request_id: {request_id}, waiting for callback... ★★★")
        
        # リクエストIDとタスクIDのマッピングを保存（将来的な拡張のため）
        request_task_mapping = getattr(app, 'request_task_mapping', {})
        request_task_mapping[request_id] = task_id
        app.request_task_mapping = request_task_mapping
        
        # コールバックデータのキーを監視する関数（task_idの形式が異なる場合に対応）
        def find_matching_callback():
            # 完全一致
            if task_id in callback_data:
                print(f"★★★ Found exact match callback for task_id: {task_id}, request_id: {request_id} ★★★")
                return callback_data[task_id]
            
            # 部分一致（タスクIDの一部が含まれるキーを探す）
            for key in callback_data.keys():
                if task_id in key or key in task_id:
                    print(f"★★★ Found callback with partial match: {key} for request_id: {request_id} ★★★")
                    return callback_data[key]
                    
            # コールバックデータ内のJSONを検索
            for key, cb in callback_data.items():
                cb_data = cb.get("data", {})
                if isinstance(cb_data, dict):
                    # data内のtask_idを確認
                    data_obj = cb_data.get("data", {})
                    if isinstance(data_obj, dict) and data_obj.get("task_id") == task_id:
                        print(f"★★★ Found task_id in nested data: {key} for request_id: {request_id} ★★★")
                        return cb
                        
            return None
            
        # 先にコールバックが来ていないか確認（すでに処理済みの場合）
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
                "message": "音楽生成が完了しました（コールバックはすでに受信済み）"
            })
        
        # コールバックを待つ
        start_time = time.time()
        while time.time() - start_time < timeout:
            # マッチするコールバックを探す
            cb_data = find_matching_callback()
            if cb_data:
                print(f"★★★ Callback found for task {task_id}, request_id: {request_id} - returning immediately without waiting for timeout ★★★")
                
                # コールバックを受信したらすぐに返す（タイムアウトを待たない）
                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "request_id": request_id,
                    "status": "completed",
                    "callback_data": cb_data,
                    "matched_callback_id": task_id,
                    "message": "音楽生成が完了しました"
                })
            
            # ステータスをチェック（エラーが出る場合はスキップ）
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
                        "message": "音楽生成が完了しました"
                    })
            except Exception as status_error:
                print(f"Status check error (non-fatal) for request_id: {request_id}: {str(status_error)}")
            
            # 一定時間待機
            time.sleep(2)
            
            # コールバックデータがあるか確認（このチェックを毎回行う）
            print(f"Waiting for callback, request_id: {request_id}, elapsed time: {int(time.time() - start_time)}s, available keys: {list(callback_data.keys())}")
        
        # タイムアウトした場合、利用可能なコールバックデータがあれば返す
        print(f"Timeout reached for request_id: {request_id}. Looking for any available callback data.")
        for key, value in callback_data.items():
            # コールバックデータの生成時刻を確認
            callback_time = datetime.fromisoformat(value.get("timestamp", ""))
            request_time = datetime.fromtimestamp(start_time)
            
            # リクエスト後に生成されたコールバックデータを探す
            if callback_time > request_time:
                print(f"Found callback data created after request: {key} for request_id: {request_id}")
                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "request_id": request_id,
                    "matched_callback_id": key,
                    "status": "completed",
                    "callback_data": value,
                    "message": "音楽生成が完了しました（タイムアウト後に見つかったコールバック）"
                })
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "request_id": request_id,
            "status": "processing",
            "message": f"タイムアウトしました。処理は続行中です。/api/check-status で状態を確認してください。"
        })
        
    except Exception as e:
        print(f"Error generating audio with callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-mp4-with-callback', methods=['POST'])
def api_generate_mp4_with_callback():
    """
    MP4ビデオを生成し、コールバックを待機するAPIエンドポイント
    """
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "無効なJSONデータ"}), 400
            
        task_id = data.get('task_id')
        audio_id = data.get('audio_id')
        author = data.get('author', 'AI Music Creator')
        domain_name = data.get('domain_name')
        timeout = data.get('timeout', 180)  # タイムアウトを3分に延長
        request_id = data.get('request_id', str(uuid.uuid4()))  # リクエスト識別用ID
        
        print(f"★★★ Received MP4 generate request with request_id: {request_id} ★★★")
        
        if not task_id:
            return jsonify({"error": "task_idは必須です"}), 400
            
        # audio_idが指定されていない場合は音楽データを確認
        if not audio_id:
            # タスクIDのコールバックデータを確認
            if task_id in callback_data:
                cb_data = callback_data[task_id].get("data", {})
                if "data" in cb_data and "data" in cb_data["data"]:
                    music_items = cb_data["data"]["data"]
                    if isinstance(music_items, list) and len(music_items) > 0:
                        # 最初の音楽アイテムのIDを使用
                        audio_id = music_items[0].get("id")
                        print(f"Using first audio ID from callback data: {audio_id} for request_id: {request_id}")
        
        if not audio_id:
            return jsonify({"error": "audio_idが指定されておらず、コールバックデータからも取得できませんでした"}), 400
            
        # 既存のMP4コールバックをクリア（重複防止）
        mp4_callbacks_to_remove = []
        for key in callback_data.keys():
            cb_data = callback_data[key].get("data", {})
            if "mp4_request_time" in cb_data and cb_data.get("original_task_id") == task_id and cb_data.get("audio_id") == audio_id:
                mp4_callbacks_to_remove.append(key)
                
        for key in mp4_callbacks_to_remove:
            print(f"Removing old MP4 callback: {key} for request_id: {request_id}")
            del callback_data[key]
        
        # MP4リクエスト時刻を記録
        mp4_request_time = datetime.now().isoformat()
        
        # 現在のcallback_dataのキーを記録（新しいコールバックの検出用）
        callback_data_keys_before = set(callback_data.keys())
        
        # MP4生成関数を呼び出す
        from modules.music.generator import generate_mp4_video
        result = generate_mp4_video(task_id, audio_id, author, domain_name)
        
        if result and "error" in result:
            return jsonify(result), 400
            
        # MP4生成のタスクID
        mp4_task_id = result.get("task_id")
        print(f"★★★ MP4 Task ID: {mp4_task_id} for request_id: {request_id}, waiting for callback... ★★★")
        
        # リクエストIDとタスクIDのマッピングを保存
        request_task_mapping = getattr(app, 'request_task_mapping', {})
        request_task_mapping[request_id] = mp4_task_id
        app.request_task_mapping = request_task_mapping
        
        # MP4リクエスト情報をグローバルに保存（コールバック照合用）
        mp4_request_info = {
            "mp4_task_id": mp4_task_id,
            "original_task_id": task_id,
            "audio_id": audio_id,
            "request_id": request_id,
            "request_time": mp4_request_time
        }
        
        # MP4のコールバックを識別するための関数
        def find_mp4_callback():
            # 完全一致（MP4タスクID）
            if mp4_task_id in callback_data:
                cb_data = callback_data[mp4_task_id]
                # 確認: コールバックデータにvideo_urlが含まれているか
                raw_data = cb_data.get("data", {})
                if "data" in raw_data and "video_url" in raw_data.get("data", {}):
                    print(f"★★★ Found MP4 callback by task_id: {mp4_task_id} for request_id: {request_id} ★★★")
                    return cb_data
            
            # コールバックデータ内を検索
            for key, cb in callback_data.items():
                if key == task_id:
                    # 元のタスクIDは音楽データの可能性が高いのでスキップ
                    continue
                    
                # リクエスト後に新しく追加されたコールバックか確認
                if key not in callback_data_keys_before:
                    print(f"Checking new callback: {key} for request_id: {request_id}")
                    
                    cb_data = cb.get("data", {})
                    
                    # MP4コールバックの特徴: video_urlキーが存在
                    if "data" in cb_data and ("video_url" in cb_data.get("data", {}) or "stream_video_url" in cb_data.get("data", {})):
                        print(f"★★★ Found MP4 callback with video URL in new callback: {key} for request_id: {request_id} ★★★")
                        return cb
                    
                    # data内のキーや値に動画関連の文字列が含まれているか確認
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
        
        # 先にコールバックが来ていないか確認
        cb_data = find_mp4_callback()
        if cb_data:
            print(f"★★★ MP4 callback already received for request_id: {request_id} - returning immediately ★★★")
            
            # コールバックデータをそのまま返す（データの中身だけ）
            raw_callback_data = cb_data.get("data", {})
            
            # ストリーミングURLが含まれていない場合は追加
            if "data" in raw_callback_data and "video_url" in raw_callback_data["data"]:
                video_url = raw_callback_data["data"]["video_url"]
                
                # ストリーミングURLがない場合は通常のURLから生成
                if "stream_video_url" not in raw_callback_data["data"]:
                    # URLを変換してストリーミングURLを追加
                    stream_url = video_url
                    if ".mp4" in video_url:
                        stream_url = video_url.replace(".mp4", "_stream.mp4")
                    
                    # ストリーミングURLを追加
                    raw_callback_data["data"]["stream_video_url"] = stream_url
                    print(f"Added stream_video_url: {stream_url} for request_id: {request_id}")
            
            # リクエストIDを追加
            if "data" in raw_callback_data:
                raw_callback_data["data"]["request_id"] = request_id
            
            # 直接コールバックデータの内容をそのまま返す
            return jsonify(raw_callback_data)
            
        # MP4のタスクIDに関連するコールバックを待つ
        start_time = time.time()
        while time.time() - start_time < timeout:
            # MP4コールバックを探す
            cb_data = find_mp4_callback()
            if cb_data:
                print(f"★★★ MP4 callback found for request_id: {request_id}, returning data ★★★")
                
                # コールバックデータをそのまま返す（データの中身だけ）
                raw_callback_data = cb_data.get("data", {})
                
                # ストリーミングURLが含まれていない場合は追加
                if "data" in raw_callback_data and "video_url" in raw_callback_data["data"]:
                    video_url = raw_callback_data["data"]["video_url"]
                    
                    # ストリーミングURLがない場合は通常のURLから生成
                    if "stream_video_url" not in raw_callback_data["data"]:
                        # URLを変換してストリーミングURLを追加
                        # 例: example.com/file.mp4 → example.com/stream/file.mp4
                        stream_url = video_url
                        if ".mp4" in video_url:
                            stream_url = video_url.replace(".mp4", "_stream.mp4")
                        
                        # ストリーミングURLを追加
                        raw_callback_data["data"]["stream_video_url"] = stream_url
                        print(f"Added stream_video_url: {stream_url} for request_id: {request_id}")
                
                # リクエストIDを追加
                if "data" in raw_callback_data:
                    raw_callback_data["data"]["request_id"] = request_id
                
                # 直接コールバックデータの内容をそのまま返す
                return jsonify(raw_callback_data)
            
            # MP4のURLをチェック
            try:
                # 状態確認APIを呼び出す
                from modules.music.generator import check_generation_status
                status_result = check_generation_status(task_id)
                
                if status_result:
                    # MP4 URLを探す
                    mp4_url = status_result.get("videoUrl")
                    
                    if mp4_url:
                        print(f"★★★ MP4 URL found via status check: {mp4_url} for request_id: {request_id} ★★★")
                        
                        # ストリーミングURLを生成
                        stream_url = mp4_url
                        if ".mp4" in mp4_url:
                            stream_url = mp4_url.replace(".mp4", "_stream.mp4")
                        
                        # コールバックデータと完全に同じ形式で返す
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
            
            # 一定時間待機
            time.sleep(2)
            
            # 進捗を表示
            print(f"Waiting for MP4 callback, request_id: {request_id}, elapsed time: {int(time.time() - start_time)}s, available keys: {list(callback_data.keys())}")
            # 定期的に新しいコールバックデータをデバッグ出力
            if int(time.time() - start_time) % 20 < 2:  # 20秒ごとに出力
                for key in callback_data.keys():
                    if key not in callback_data_keys_before:
                        print(f"New callback data found for key {key} for request_id: {request_id}: {json.dumps(callback_data[key].get('data', {}), ensure_ascii=False)[:200]}...")
        
        # タイムアウトした場合
        return jsonify({
            "code": 408,
            "data": {
                "task_id": mp4_task_id,
                "request_id": request_id,
                "status": "processing"
            },
            "msg": f"MP4生成がタイムアウトしました（request_id: {request_id}）。処理は続行中です。"
        })
        
    except Exception as e:
        print(f"MP4生成APIでエラーが発生: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "code": 500,
            "data": None,
            "msg": f"エラーが発生しました: {str(e)}"
        }), 500

@app.route('/api/generate-video', methods=['POST'])
async def generate_video():
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # パラメータを取得（オプショナルなものはデフォルト値を設定）
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
            
        aspect_ratio = data.get('aspect_ratio', '9:16')
        duration = data.get('duration', 8)
        style = data.get('style', 'cyberpunk')
        
        # 動画生成を実行
        from modules.video.generator import generate_video_from_text
        result = await generate_video_from_text(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration=duration,
            style=style
        )
        
        # 成功レスポンスを返す
        return jsonify(result)
        
    except Exception as e:
        print(f"Error generating video: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/merge-video-audio', methods=['POST'])
def merge_video_audio_endpoint():

    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # 必須パラメータの確認
        video_url = data.get('video_url')
        audio_url = data.get('audio_url')
        
        if not video_url or not audio_url:
            return jsonify({"error": "video_url and audio_url are required"}), 400
        
        # 動画と音声をマージ
        result = merge_video_audio(
            video_url=video_url,
            audio_url=audio_url
        )
        
        if not result.get('success'):
            return jsonify(result), 500
        
        # 成功レスポンスを返す
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
        # Webhookデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        print(f"Received Segmind webhook: {json.dumps(data, ensure_ascii=False)}")
        
        # イベントタイプを確認
        event_type = data.get('event_type')
        if not event_type:
            return jsonify({"error": "event_type is required"}), 400
        
        # イベントタイプに応じた処理
        if event_type == 'NODE_RUN':
            # ノード実行イベントの処理
            node_id = data.get('node_id')
            status = data.get('status')
            output_url = data.get('output_url')
            
            print(f"Node {node_id} status: {status}")
            if output_url:
                print(f"Output URL: {output_url}")
            
            # ここで必要な処理を実行
            # 例: 出力URLを保存、次の処理を実行など
            
        elif event_type == 'GRAPH_RUN':
            # ワークフロー完了イベントの処理
            graph_id = data.get('graph_id')
            status = data.get('status')
            outputs = data.get('outputs', {})
            
            print(f"Graph {graph_id} completed with status: {status}")
            print(f"Outputs: {json.dumps(outputs, ensure_ascii=False)}")
            
            # ここで必要な処理を実行
            # 例: 最終結果の保存、通知の送信など
        
        # 成功レスポンスを返す
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
    # 環境変数からポート番号を取得（デフォルトは5001）
    port = int(os.environ.get("PORT", 5001))
    
    print(f"Starting server at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)