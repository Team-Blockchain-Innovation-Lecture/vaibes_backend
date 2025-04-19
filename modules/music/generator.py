import os
import time
import json
import requests
import uuid
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# 環境変数を読み込む
load_dotenv()

# Suno API設定
SUNO_API_KEY = os.getenv("SUNO_API_KEY")
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:5001/callback")
BASE_URL = "https://apibox.erweima.ai"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def call_suno_api(endpoint, data, max_retries=3, retry_delay=5):
    """
    Suno APIを呼び出す共通関数（リトライ機能付き）
    
    Args:
        endpoint: APIエンドポイント
        data: リクエストデータ
        max_retries: 最大リトライ回数
        retry_delay: リトライ間の待機時間（秒）
        
    Returns:
        APIレスポンス
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
            print(f"Response body: {response.text[:500]}...")  # 長いレスポンスは省略
            
            # 503エラーの場合はリトライ
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
            
            # APIのレスポンス形式に合わせてエラーチェック
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
    
    # すべてのリトライが失敗した場合
    if last_exception:
        raise last_exception
    else:
        raise Exception("Maximum retries exceeded")

def generate_music_with_suno(prompt, reference_style=None, with_lyrics=True, model_version="v4", wait_for_completion=False, max_wait_time=300):
    """
    Suno APIを使用して音楽を生成する関数
    
    Args:
        prompt: 音楽生成のプロンプト
        reference_style: 参照スタイル（ジャンルなど）
        with_lyrics: 歌詞を含めるかどうか（デフォルトはTrue）
        model_version: モデルバージョン（v3.5, v4など）
        wait_for_completion: 生成完了を待つかどうか
        max_wait_time: 最大待機時間（秒）
        
    Returns:
        生成された音楽の情報、またはエラー情報を含む辞書
    """
    try:
        print(f"\nGenerating music with Suno API...")
        print(f"Prompt: '{prompt}'")
        print(f"Reference style: {reference_style}")
        print(f"With lyrics: {with_lyrics}")
        print(f"Model version: {model_version}")
        print(f"Wait for completion: {wait_for_completion}")
        
        # APIキーの確認
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return {"error": "SUNO_API_KEY is not set in environment variables"}
            
        print(f"SUNO_API_KEY: {SUNO_API_KEY[:5]}...{SUNO_API_KEY[-5:] if SUNO_API_KEY else ''}")
        
        # APIエンドポイント
        api_endpoint = "/api/v1/generate"
        
        # モデルバージョンのフォーマット - 修正
        # Suno APIが受け付ける正確な形式に変換
        if model_version.lower() == "v3.5" or model_version.lower() == "v3_5" or model_version == "3.5":
            formatted_model = "V3_5"  # 大文字V、アンダースコア
        elif model_version.lower() == "v4" or model_version == "4":
            formatted_model = "V4"    # 大文字V
        else:
            # デフォルトはV4
            formatted_model = "V4"
            
        print(f"Formatted model: {formatted_model}")
        
        # タスクIDの生成（一意の識別子）
        task_id = str(uuid.uuid4())
        
        # コールバックURLの設定 - httpsからhttpに修正
        callback_url = CALLBACK_URL
        if callback_url.startswith("http://"):
            callback_url = callback_url.replace("http://", "https://")
        print(f"Callback URL: {callback_url}")
        # ローカル開発環境の場合、コールバックURLを確認
        if "localhost" in callback_url or "127.0.0.1" in callback_url:
            print(f"警告: ローカルURLへのコールバックは外部から到達できない可能性があります: {callback_url}")
            print("ngrokなどのトンネリングサービスの使用を検討してください")
        
        print(f"Callback URL: {callback_url}")
        
        # 歌詞付き音楽生成の場合、プロンプトに歌詞に関する指示を追加
        enhanced_prompt = prompt
        if with_lyrics and "歌詞" not in prompt and "lyrics" not in prompt.lower():
            # プロンプトに歌詞に関する指示がない場合、自動的に追加
            if "日本語" in prompt or "Japanese" in prompt:
                enhanced_prompt += "。日本語の歌詞を含めてください。"
            else:
                enhanced_prompt += ". Include meaningful lyrics."
            print(f"Enhanced prompt for lyrics: '{enhanced_prompt}'")
        
        # リクエストデータを準備（Suno APIのドキュメントに基づく正しい形式）
        data = {
            "prompt": enhanced_prompt,
            "style": reference_style if reference_style else "",
            "title": f"Generated Music {task_id[:8]}",
            "customMode": True,
            "instrumental": not with_lyrics,
            "model": formatted_model,
            "taskId": task_id,
            "callBackUrl": callback_url
        }
        
        # 否定的なタグがあれば追加（オプション）
        negative_tags = os.getenv("SUNO_NEGATIVE_TAGS", "")
        if negative_tags:
            data["negativeTags"] = negative_tags
        
        print(f"Request data: {json.dumps(data, ensure_ascii=False)}")
        
        # APIリクエストを送信
        try:
            response_data = call_suno_api(api_endpoint, data)
            print(f"Response data: {json.dumps(response_data, ensure_ascii=False)}")
            
            # 成功レスポンスの処理
            if response_data.get("code") == 200:
                result = {
                    "success": True,
                    "status": "pending",
                    "task_id": task_id,
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
    タスクの状態を確認する関数
    
    Args:
        task_id: タスクID
        
    Returns:
        タスクの状態情報
    """
    try:
        print(f"\nChecking status for task {task_id}...")
        
        # APIキーの確認
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return None
        
        # リクエストデータを準備
        data = {
            "taskId": task_id
        }
        
        # 状態確認APIを呼び出す - 正しいエンドポイントを使用
        result = call_suno_api("/api/v1/status", data, max_retries=1)
        
        # レスポンスからデータを取得
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
    生成された音楽のWAV形式を取得する関数
    
    Args:
        task_id: タスクID
        
    Returns:
        WAV形式のURL
    """
    try:
        print(f"\nGetting WAV format for task {task_id}...")
        
        # 状態を確認して完了しているか確認
        status_result = check_generation_status(task_id)
        if not status_result or status_result.get("status") != "success":
            print("ERROR: Task not completed")
            return None
            
        # WAV URLを取得
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
    Suno APIを使用してMP4ビデオを生成する関数
    
    Args:
        task_id: タスクID
        audio_id: 音声ID（指定しない場合はタスクIDから取得）
        author: 作者名
        domain_name: ドメイン名
        
    Returns:
        生成されたMP4ビデオのURL
    """
    try:
        print(f"\nGenerating MP4 video for task {task_id}...")
        
        # APIキーの確認
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return {"error": "SUNO_API_KEY is not set in environment variables"}
        
        # 音声IDが指定されていない場合は、タスクIDから状態を確認して取得
        if not audio_id:
            status_result = check_generation_status(task_id)
            if not status_result or status_result.get("status") != "success":
                print("ERROR: Task not completed or audio_id not available")
                return {"error": "Task not completed or audio_id not available"}
                
            # 音声IDを取得（APIレスポンスの形式に依存）
            if "data" in status_result and isinstance(status_result["data"], list) and len(status_result["data"]) > 0:
                audio_id = status_result["data"][0].get("id")
            
            if not audio_id:
                print("ERROR: Could not find audio_id in task status")
                return {"error": "Could not find audio_id in task status"}
        
        # コールバックURLの設定
        callback_url = os.getenv("CALLBACK_URL")
        if not callback_url:
            print("WARNING: CALLBACK_URL is not set")
            callback_url = "http://localhost:5001/callback"
        
        # ドメイン名が指定されていない場合はデフォルト値を使用
        if not domain_name:
            domain_name = "music.example.com"
        
        # リクエストデータを準備
        data = {
            "taskId": task_id,
            "audioId": audio_id,
            "callBackUrl": callback_url,
            "author": author,
            "domainName": domain_name
        }
        
        print(f"MP4 generation request data: {json.dumps(data, ensure_ascii=False)}")
        
        # MP4生成APIを呼び出す
        result = call_suno_api("/api/v1/mp4/generate", data)
        
        # レスポンスを処理
        response_data = result.get("data", {})
        
        # 成功レスポンスの処理
        if result.get("code") == 200:
            print(f"MP4 generation request submitted successfully")
            
            # レスポンスからMP4 URLを取得
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
                # MP4 URLがない場合は、タスクIDを返して後で確認できるようにする
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
    Suno APIを使用して歌詞を生成する関数
    
    Args:
        prompt: 歌詞生成のプロンプト
        
    Returns:
        生成された歌詞
    """
    try:
        print(f"\nGenerating lyrics with Suno API...")
        print(f"Prompt: '{prompt}'")
        
        # APIキーの確認
        if not SUNO_API_KEY:
            print("ERROR: SUNO_API_KEY is not set")
            return None
        
        # タスクIDを生成
        task_id = str(uuid.uuid4())
        
        # リクエストデータを準備
        data = {
            "prompt": prompt,
            "taskId": task_id
        }
        
        # 歌詞生成APIを呼び出す
        result = call_suno_api("/api/v1/lyrics", data)
        
        # レスポンスから歌詞を取得
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
    URLからファイルをダウンロードする関数
    
    Args:
        url: ダウンロードするURL
        filename: 保存するファイル名（指定しない場合は自動生成）
        output_dir: 出力ディレクトリ（指定しない場合はデフォルト）
        
    Returns:
        ローカルファイルパス
    """
    try:
        if not output_dir:
            output_dir = OUTPUT_DIR
            
        if not filename:
            # URLからファイル名を取得するか、UUIDを使用
            filename = os.path.basename(url.split('?')[0]) or f"file_{uuid.uuid4()}"
        
        local_path = os.path.join(output_dir, filename)
        
        print(f"\nDownloading file from {url} to {local_path}...")
        
        # ファイルをダウンロード
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