import os
import time
import json
import uuid
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv
from datetime import datetime

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
                "path": "/dashboard",
                "method": "GET",
                "description": "シンプルなダッシュボードを表示するエンドポイント"
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
def generate_music():
    try:
        # リクエストからデータを取得
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
            
        print(f"Received data: {data}")
        
        prompt = data.get('prompt', '')
        reference_style = data.get('genre', '')
        instrumental = data.get('instrumental', False)  # instrumentalパラメータを直接取得
        with_lyrics = not instrumental  # instrumentalの逆がwith_lyrics
        model_version = data.get('model_version', 'v4')
        
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
            
        # 音楽生成モジュールを呼び出す
        from modules.music.generator import generate_music_with_suno
        
        result = generate_music_with_suno(prompt, reference_style, with_lyrics, model_version)
        
        if not result:
            return jsonify({"error": "Music generation failed"}), 500
        
        # 処理中の場合でも成功レスポンスを返す
        status = result.get("status", "success")
        
        return jsonify({
            "success": True,
            "status": status,
            "audio_url": result.get("audio_url"),
            "lyrics": result.get("lyrics"),
            "cover_image_url": result.get("cover_image_url"),
            "task_id": result.get("task_id"),
            "prompt": prompt,
            "message": "Music generation request accepted. Use the task_id to check status." if status == "pending" else "Music generation completed."
        })
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
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

# 接続テストエンドポイント
@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    try:
        import requests
        
        # APIキーの確認
        suno_api_key = os.getenv("SUNO_API_KEY")
        if not suno_api_key:
            return jsonify({"error": "SUNO_API_KEY is not set"}), 500
            
        # APIキーの最初と最後の数文字だけを表示（セキュリティのため）
        masked_key = f"{suno_api_key[:5]}...{suno_api_key[-5:]}" if len(suno_api_key) > 10 else "***"
        
        # Suno APIに接続テスト
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {suno_api_key}"
        }
        
        # 公式APIのエンドポイントを使用
        base_url = "https://apibox.erweima.ai"
        
        # ユーザー情報を取得（軽量なリクエスト）
        response = requests.get(f"{base_url}/v1/generate", headers=headers)
        
        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text,
            "key_preview": masked_key
        })
        
    except Exception as e:
        print(f"Connection test failed: {str(e)}")
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
    """
    Suno APIからのコールバックを受け取るエンドポイント
    GETリクエストの場合は最新のコールバックデータを表示
    POSTリクエストの場合はコールバックデータを保存
    """
    # GETリクエストの場合
    if request.method == 'GET':
        # 最新のコールバックデータを取得
        if not callback_data:
            return jsonify({
                "status": "No callback data available",
                "message": "No callbacks have been received yet"
            })
        
        # 最新のタスクIDを取得
        latest_task_id = max(callback_data.keys(), key=lambda k: callback_data[k].get("timestamp", ""))
        latest_data = callback_data[latest_task_id]
        
        return jsonify({
            "status": "success",
            "message": "Latest callback data",
            "task_id": latest_task_id,
            "timestamp": latest_data.get("timestamp"),
            "data": latest_data.get("data")
        })
    
    # POSTリクエストの場合
    try:
        # リクエストデータを取得
        data = request.get_json()
        if not data:
            print("Error: Invalid JSON data in callback")
            return jsonify({"error": "Invalid JSON data"}), 400
        
        print(f"Received callback data: {json.dumps(data, ensure_ascii=False)}")
        
        # タスクIDを取得
        task_id = data.get("data", {}).get("task_id")
        if not task_id:
            print("Error: No task_id in callback data")
            return jsonify({"error": "No task_id in callback data"}), 400
        
        # コールバックデータを保存
        callback_data[task_id] = {
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"Stored callback data for task_id: {task_id}")
        
        # 成功レスポンスを返す
        return jsonify({
            "success": True,
            "message": "Callback received and processed successfully"
        })
        
    except Exception as e:
        print(f"Error in callback endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/callbacks', methods=['GET'])
def list_callbacks():
    """
    保存されているすべてのコールバックデータを一覧表示するエンドポイント
    """
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

@app.route('/callback/<task_id>', methods=['GET'])
def get_callback(task_id):
    """
    特定のタスクIDに対するコールバックデータを取得するエンドポイント
    """
    if task_id not in callback_data:
        return jsonify({
            "status": "not_found",
            "message": f"No callback data found for task_id: {task_id}"
        }), 404
    
    return jsonify({
        "status": "success",
        "message": f"Callback data for task_id: {task_id}",
        "task_id": task_id,
        "timestamp": callback_data[task_id].get("timestamp"),
        "data": callback_data[task_id].get("data")
    })

@app.route('/simulate-callback', methods=['POST'])
def simulate_callback():
    """
    コールバックをシミュレートするエンドポイント
    """
    try:
        # リクエストデータを取得
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # タスクIDを取得または生成
        task_id = request_data.get("task_id", f"simulated_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # シミュレートするコールバックデータを作成
        simulated_data = {
            "code": 200,
            "msg": "All generated successfully.",
            "data": {
                "callbackType": "complete",
                "task_id": task_id,
                "data": [
                    {
                        "id": f"simulated_item_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        "audio_url": "https://example.com/simulated.mp3",
                        "source_audio_url": "https://example.com/simulated.mp3",
                        "image_url": "https://example.com/simulated.jpg",
                        "title": request_data.get("title", "Simulated Music"),
                        "duration": request_data.get("duration", 180)
                    }
                ]
            }
        }
        
        # コールバックデータを保存
        callback_data[task_id] = {
            "data": simulated_data,
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify({
            "success": True,
            "message": "Simulated callback created",
            "task_id": task_id,
            "data": simulated_data
        })
        
    except Exception as e:
        print(f"Error in simulate-callback endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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

if __name__ == '__main__':
    # 環境変数からポート番号を取得（デフォルトは5001）
    port = int(os.environ.get("PORT", 5001))
    
    print(f"Starting server at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)