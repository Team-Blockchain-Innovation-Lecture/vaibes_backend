import requests
import argparse
import time
import os
import json
import base64
import webbrowser
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import http.server
import socketserver
import threading

# .envファイルから環境変数を読み込む
load_dotenv()

# 出力ディレクトリ
OUTPUT_DIR = "generated_music"

def generate_music(prompt, output_dir=OUTPUT_DIR, duration=10, model="facebook/musicgen-small"):
    """
    Hugging Face Inference APIを使用して音楽を生成する
    
    Args:
        prompt (str): 音楽生成のためのプロンプト
        output_dir (str): 出力ディレクトリ
        duration (int): 生成する音楽の長さ（秒）
        model (str): 使用するモデル名
    
    Returns:
        str: 生成された音楽のファイルパス
    """
    # Hugging Face APIトークン
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
    if not HF_API_TOKEN:
        print("エラー: HF_API_TOKENが設定されていません。.envファイルを確認してください。")
        print("Hugging Faceのウェブサイト(https://huggingface.co/settings/tokens)からトークンを取得してください。")
        return None
    
    # 出力ディレクトリが存在しない場合は作成
    os.makedirs(output_dir, exist_ok=True)
    
    # 現在の日時を含むファイル名を生成
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prompt = "".join(c if c.isalnum() else "_" for c in prompt[:30])
    output_file = os.path.join(output_dir, f"{timestamp}_{safe_prompt}.mp3")
    
    # APIエンドポイント
    API_URL = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 250,
            "duration": duration
        }
    }
    
    print(f"音楽生成リクエストを送信中...")
    print(f"プロンプト: {prompt}")
    print(f"モデル: {model}")
    print(f"生成時間: {duration}秒")
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # リクエストを送信
            response = requests.post(API_URL, headers=headers, json=payload)
            
            if response.status_code == 200:
                # 音声データを保存
                with open(output_file, "wb") as f:
                    f.write(response.content)
                print(f"音声を保存しました: {output_file}")
                return output_file
            else:
                print(f"APIエラー: ステータスコード {response.status_code}")
                print(f"レスポンス: {response.text}")
                
                # モデルがロード中の場合は再試行
                if response.status_code == 503 and "loading" in response.text.lower():
                    retry_count += 1
                    wait_time = 10 * retry_count
                    print(f"モデルをロード中です。{wait_time}秒後に再試行します... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    break
        
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"10秒後に再試行します... ({retry_count}/{max_retries})")
                time.sleep(10)
            else:
                break
    
    print("音楽生成に失敗しました。")
    return None

def create_html_player(music_files):
    """
    生成された音楽を再生するためのHTMLプレーヤーを作成する
    
    Args:
        music_files (list): 音楽ファイルのリスト
    
    Returns:
        str: HTMLファイルのパス
    """
    html_file = os.path.join(OUTPUT_DIR, "music_player.html")
    
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>生成された音楽プレーヤー</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .music-item {
                background-color: white;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .prompt {
                font-weight: bold;
                margin-bottom: 10px;
            }
            .timestamp {
                color: #666;
                font-size: 0.8em;
                margin-bottom: 10px;
            }
            audio {
                width: 100%;
                margin-top: 10px;
            }
            .download-link {
                display: inline-block;
                margin-top: 10px;
                color: #0066cc;
                text-decoration: none;
            }
            .download-link:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>生成された音楽</h1>
    """
    
    # 音楽ファイルごとにプレーヤーを追加
    for file_path in music_files:
        file_name = os.path.basename(file_path)
        parts = file_name.split('_', 2)
        
        if len(parts) >= 3:
            date_str = parts[0]
            time_str = parts[1]
            prompt = parts[2].replace('.mp3', '').replace('_', ' ')
            timestamp = f"{date_str} {time_str}"
        else:
            timestamp = "不明"
            prompt = file_name.replace('.mp3', '').replace('_', ' ')
        
        relative_path = os.path.relpath(file_path, OUTPUT_DIR)
        
        html_content += f"""
        <div class="music-item">
            <div class="prompt">{prompt}</div>
            <div class="timestamp">生成日時: {timestamp}</div>
            <audio controls src="{relative_path}"></audio>
            <a href="{relative_path}" download class="download-link">ダウンロード</a>
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return html_file

def start_http_server(directory=OUTPUT_DIR, port=8000):
    """
    HTTPサーバーを起動する
    
    Args:
        directory (str): 提供するディレクトリ
        port (int): ポート番号
    """
    handler = http.server.SimpleHTTPRequestHandler
    
    class CustomHandler(handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
    
    with socketserver.TCPServer(("", port), CustomHandler) as httpd:
        print(f"HTTPサーバーを起動しました: http://localhost:{port}")
        httpd.serve_forever()

def main():
    parser = argparse.ArgumentParser(description="音楽を生成してダウンロードします")
    parser.add_argument("prompt", nargs="?", help="音楽生成のためのプロンプト")
    parser.add_argument("--duration", type=int, default=10, help="生成する音楽の長さ（秒）")
    parser.add_argument("--model", default="facebook/musicgen-small", 
                        choices=["facebook/musicgen-small", "facebook/musicgen-medium", "facebook/musicgen-large"],
                        help="使用するモデル")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="出力ディレクトリ")
    parser.add_argument("--port", type=int, default=8000, help="HTTPサーバーのポート番号")
    parser.add_argument("--play", action="store_true", help="生成後に音楽プレーヤーを開く")
    
    args = parser.parse_args()
    
    # プロンプトが指定されていない場合は対話モード
    if args.prompt is None:
        print("音楽生成プロンプトを入力してください（終了するには 'exit' と入力）:")
        
        # HTTPサーバーをバックグラウンドで起動
        server_thread = threading.Thread(target=start_http_server, args=(args.output_dir, args.port), daemon=True)
        server_thread.start()
        
        # 既存の音楽ファイルを取得
        music_files = [os.path.join(args.output_dir, f) for f in os.listdir(args.output_dir) 
                      if f.endswith('.mp3') and os.path.isfile(os.path.join(args.output_dir, f))]
        
        # 音楽プレーヤーを作成して開く
        if music_files:
            player_file = create_html_player(music_files)
            player_url = f"http://localhost:{args.port}/{os.path.basename(player_file)}"
            print(f"音楽プレーヤーを開きます: {player_url}")
            webbrowser.open(player_url)
        
        while True:
            prompt = input("> ")
            if prompt.lower() == 'exit':
                break
            
            # 音楽を生成
            music_file = generate_music(prompt, args.output_dir, args.duration, args.model)
            
            if music_file:
                # 音楽ファイルのリストを更新
                music_files = [os.path.join(args.output_dir, f) for f in os.listdir(args.output_dir) 
                              if f.endswith('.mp3') and os.path.isfile(os.path.join(args.output_dir, f))]
                
                # 音楽プレーヤーを更新して開く
                player_file = create_html_player(music_files)
                player_url = f"http://localhost:{args.port}/{os.path.basename(player_file)}"
                print(f"音楽プレーヤーを更新しました: {player_url}")
                webbrowser.open(player_url)
    else:
        # 音楽を生成
        music_file = generate_music(args.prompt, args.output_dir, args.duration, args.model)
        
        if music_file and args.play:
            # 音楽ファイルのリストを取得
            music_files = [os.path.join(args.output_dir, f) for f in os.listdir(args.output_dir) 
                          if f.endswith('.mp3') and os.path.isfile(os.path.join(args.output_dir, f))]
            
            # 音楽プレーヤーを作成
            player_file = create_html_player(music_files)
            
            # HTTPサーバーを起動
            server_thread = threading.Thread(target=start_http_server, args=(args.output_dir, args.port), daemon=True)
            server_thread.start()
            
            # ブラウザで音楽プレーヤーを開く
            player_url = f"http://localhost:{args.port}/{os.path.basename(player_file)}"
            print(f"音楽プレーヤーを開きます: {player_url}")
            webbrowser.open(player_url)
            
            # メインスレッドを維持
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("プログラムを終了します...")

if __name__ == "__main__":
    main() 