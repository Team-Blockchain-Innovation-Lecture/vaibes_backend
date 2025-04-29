import os
import fal_client
import requests
from pydub import AudioSegment

# APIキーを環境変数から取得
FAL_KEY = os.getenv("FAL_KEY")
if not FAL_KEY:
    raise ValueError("FAL_KEY environment variable is not set")

fal_client.api_key = FAL_KEY

# モデルID
MODEL_ID = "fal-ai/pixverse/v4/text-to-video"

# コールバックURLを環境変数から取得
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:5001/callback")

# Segmind API設定
SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY", "SG_4d5d5ba221ccfc4e")
SEGMIND_API_URL = "https://api.segmind.com/v1/video-audio-merge"

def generate_video_from_text(
    prompt: str,
    aspect_ratio: str = "9:16",
    duration: int = 8,
    style: str = "cyberpunk"
) -> dict:
    """
    文字列プロンプトから動画を生成し、結果を返す

    :param prompt: 動画生成用のテキストプロンプト
    :param aspect_ratio: アスペクト比（例: "9:16"）
    :param duration: 動画の長さ（秒）
    :param style: 動画のスタイル
    :return: APIのレスポンス（dict）
    """
    input_data = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "style": style,
        "webhook_url": CALLBACK_URL
    }

    handler = fal_client.submit(
        MODEL_ID,
        arguments=input_data
    )
    result = handler.get()
    return result

def merge_video_audio(
    video_url: str,
    audio_url: str,
    video_start: int = 0,
    video_end: int = -1,
    audio_start: int = 0,
    audio_end: int = -1,
    audio_fade_in: int = 0,
    audio_fade_out: int = 0,
    override_audio: bool = False,
    merge_intensity: float = 0.5,
    output_path: str = "result.mp4"
) -> dict:
    """
    動画と音声をマージする

    :param video_url: 動画のURL
    :param audio_url: 音声のURL
    :param video_start: 動画の開始位置（秒）
    :param video_end: 動画の終了位置（秒、-1は最後まで）
    :param audio_start: 音声の開始位置（秒）
    :param audio_end: 音声の終了位置（秒、-1は最後まで）
    :param audio_fade_in: 音声のフェードイン時間（秒）
    :param audio_fade_out: 音声のフェードアウト時間（秒）
    :param override_audio: 既存の音声を上書きするかどうか
    :param merge_intensity: マージの強度（0.0-1.0）
    :param output_path: 出力ファイルのパス
    :return: 処理結果（dict）
    """
    try:
        # 音声ファイルをダウンロード
        audio_response = requests.get(audio_url)
        audio_response.raise_for_status()
        
        # 一時的な音声ファイルを作成
        temp_audio_path = "temp_audio.mp3"
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_response.content)
        
        # 音声を読み込み
        audio = AudioSegment.from_file(temp_audio_path)
        
        # 音声を8秒に切り取る
        audio = audio[:8000]  # 8秒 = 8000ミリ秒
        
        # 切り取った音声を保存
        trimmed_audio_path = "trimmed_audio.mp3"
        audio.export(trimmed_audio_path, format="mp3")
        
        # Webhook URLを構築
        webhook_url = f"{CALLBACK_URL}/api/webhook/segmind"
        
        # リクエストデータを準備
        data = {
            "input_video": video_url,
            "input_audio": trimmed_audio_path,
            "video_start": video_start,
            "video_end": video_end,
            "audio_start": 0,  # 切り取った音声は最初から使用
            "audio_end": -1,   # 最後まで使用
            "audio_fade_in": audio_fade_in,
            "audio_fade_out": audio_fade_out,
            "override_audio": override_audio,
            "merge_intensity": merge_intensity,
            "webhook_url": webhook_url
        }

        headers = {'x-api-key': SEGMIND_API_KEY}

        # APIリクエストを送信
        response = requests.post(SEGMIND_API_URL, json=data, headers=headers)
        response.raise_for_status()

        # 結果をファイルに保存
        with open(output_path, 'wb') as f:
            f.write(response.content)

        # 一時ファイルを削除
        os.remove(temp_audio_path)
        os.remove(trimmed_audio_path)

        return {
            "success": True,
            "message": "Video and audio merged successfully",
            "output_path": output_path
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to merge video and audio"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred"
        } 