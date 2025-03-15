from flask import Flask, request, jsonify, render_template
import requests
import os
import json
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# Suno AI APIの設定
SUNO_API_KEY = os.environ.get("SUNO_API_KEY")
SUNO_API_URL = "https://api.suno.ai/v1/generations"

@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/generate-music', methods=['POST'])
def generate_music():
    data = request.json
    prompt = data.get('prompt', '')
    
    if not prompt:
        return jsonify({"error": "プロンプトが必要です"}), 400
    
    if not SUNO_API_KEY:
        return jsonify({"error": "API KEYが設定されていません"}), 500
    
    # Suno AI APIにリクエストを送信
    headers = {
        "Authorization": f"Bearer {SUNO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "model": "suno-v3-beta"  # 使用するモデルを指定
    }
    
    try:
        response = requests.post(SUNO_API_URL, headers=headers, json=payload)
        
        # デバッグ情報を出力
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        # ステータスコードをチェック
        if response.status_code != 200:
            return jsonify({
                "error": f"APIエラー: ステータスコード {response.status_code}",
                "details": response.text
            }), 500
        
        # レスポンスが空でないことを確認
        if not response.text.strip():
            return jsonify({"error": "APIからの応答が空です"}), 500
        
        # JSONパースを試みる
        try:
            result = response.json()
            return jsonify(result)
        except json.JSONDecodeError as e:
            return jsonify({
                "error": f"JSONパースエラー: {str(e)}",
                "raw_response": response.text
            }), 500
            
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"APIリクエストエラー: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)