import os
import time
import json
import uuid
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv
from datetime import datetime
from modules.music.generator import generate_music_with_suno

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
            
        # タスクIDを取得
        task_id = result.get('task_id')
        
        # 即時レスポンスを返す（非同期処理に変更）
        return jsonify({
            "success": True,
            "task_id": task_id,
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
        
        print(f"Received callback data: {json.dumps(data, ensure_ascii=False)}")
        
        # タスクIDを取得（Sunoのコールバック形式に合わせる）
        task_id = None
        if "data" in data and "task_id" in data["data"]:
            task_id = data["data"]["task_id"]
        elif "taskId" in data:
            task_id = data["taskId"]
        elif "task_id" in data:
            task_id = data["task_id"]
            
        if not task_id:
            print(f"Warning: No task_id in callback data, searching in nested data")
            # データ内を再帰的に検索
            def find_task_id(obj):
                if isinstance(obj, dict):
                    if "task_id" in obj:
                        return obj["task_id"]
                    for k, v in obj.items():
                        result = find_task_id(v)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_task_id(item)
                        if result:
                            return result
                return None
                
            task_id = find_task_id(data)
            
        if not task_id:
            print(f"Warning: No task_id found in callback data")
            # 一時的なIDを生成
            task_id = str(uuid.uuid4())
            print(f"Generated temporary task_id: {task_id}")
        else:
            print(f"Found task_id in callback data: {task_id}")
        
        # コールバックデータを保存
        callback_data[task_id] = {
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"Stored callback data for task_id: {task_id}")
        return jsonify({"success": True, "task_id": task_id})
        
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
        
        if task_id not in callback_data:
            print(f"Task ID {task_id} not found in callback_data")
            return jsonify({
                "status": "not_found",
                "message": f"No callback data found for task_id: {task_id}",
                "available_tasks": list(callback_data.keys())
            }), 404
        
        print(f"Found callback data for task_id: {task_id}")
        return jsonify({
            "status": "success",
            "message": f"Callback data for task_id: {task_id}",
            "task_id": task_id,
            "timestamp": callback_data[task_id].get("timestamp"),
            "data": callback_data[task_id].get("data")
        })
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
        timeout = data.get('timeout', 120)  # タイムアウトを2分に延長
        
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
        print(f"Task ID: {task_id}, waiting for callback...")
        
        # コールバックデータのキーを監視する関数（task_idの形式が異なる場合に対応）
        def find_matching_callback():
            # 完全一致
            if task_id in callback_data:
                return callback_data[task_id]
            
            # 部分一致（タスクIDの一部が含まれるキーを探す）
            for key in callback_data.keys():
                if task_id in key or key in task_id:
                    print(f"Found callback with partial match: {key}")
                    return callback_data[key]
                    
            # コールバックデータ内のJSONを検索
            for key, cb in callback_data.items():
                cb_data = cb.get("data", {})
                if isinstance(cb_data, dict):
                    # data内のtask_idを確認
                    data_obj = cb_data.get("data", {})
                    if isinstance(data_obj, dict) and data_obj.get("task_id") == task_id:
                        print(f"Found task_id in nested data: {key}")
                        return cb
                        
            return None
        
        # コールバックを待つ
        start_time = time.time()
        while time.time() - start_time < timeout:
            # マッチするコールバックを探す
            cb_data = find_matching_callback()
            if cb_data:
                print(f"Callback found for task {task_id}")
                
                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "status": "completed",
                    "callback_data": cb_data,
                    "message": "音楽生成が完了しました"
                })
            
            # ステータスをチェック（エラーが出る場合はスキップ）
            try:
                from modules.music.generator import check_generation_status
                status_result = check_generation_status(task_id)
                
                if status_result and status_result.get("status") == "success":
                    print(f"Task {task_id} completed successfully (via status check)")
                    return jsonify({
                        "success": True,
                        "task_id": task_id,
                        "status": "completed",
                        "result": status_result,
                        "message": "音楽生成が完了しました"
                    })
            except Exception as status_error:
                print(f"Status check error (non-fatal): {str(status_error)}")
            
            # 一定時間待機
            time.sleep(2)
            
            # コールバックデータがあるか確認（このチェックを毎回行う）
            print(f"Waiting for callback, elapsed time: {int(time.time() - start_time)}s, available keys: {list(callback_data.keys())}")
        
        # タイムアウトした場合、利用可能なコールバックデータがあれば返す
        print(f"Timeout reached. Looking for any available callback data.")
        for key, value in callback_data.items():
            # コールバックデータの生成時刻を確認
            callback_time = datetime.fromisoformat(value.get("timestamp", ""))
            request_time = datetime.fromtimestamp(start_time)
            
            # リクエスト後に生成されたコールバックデータを探す
            if callback_time > request_time:
                print(f"Found callback data created after request: {key}")
                return jsonify({
                    "success": True,
                    "task_id": task_id,
                    "matched_callback_id": key,
                    "status": "completed",
                    "callback_data": value,
                    "message": "音楽生成が完了しました（タイムアウト後に見つかったコールバック）"
                })
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "status": "processing",
            "message": f"タイムアウトしました。処理は続行中です。/api/check-status で状態を確認してください。"
        })
        
    except Exception as e:
        print(f"Error generating audio with callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 環境変数からポート番号を取得（デフォルトは5001）
    port = int(os.environ.get("PORT", 5001))
    
    print(f"Starting server at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)