import os
import fal_client
import requests
import logging
from pydub import AudioSegment
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
import ffmpeg
import random
import boto3
import uuid
import hashlib
from botocore.exceptions import ClientError

# ロギングの基本設定
logging.basicConfig(
    level=logging.DEBUG,  # DEBUGレベル以上のログを出力
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# APIキーを環境変数から取得
FAL_KEY = os.getenv("FAL_KEY")
if not FAL_KEY:
    raise ValueError("FAL_KEY environment variable is not set")

fal_client.api_key = FAL_KEY

# モデルID
MODEL_ID = "fal-ai/pixverse/v4/text-to-video"

# コールバックURLを環境変数から取得
CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:5001")

# Segmind API設定
SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY", "SG_4d5d5ba221ccfc4e")
SEGMIND_API_URL = "https://api.segmind.com/v1/video-audio-merge"

# 利用可能なスタイル
AVAILABLE_STYLES = ["anime", "3d_animation", "clay", "comic", "cyberpunk"]

async def generate_video_from_text(
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
    :param style: 動画のスタイル (選択肢: "anime", "3d_animation", "clay", "comic", "cyberpunk")
    :return: APIのレスポンス（dict）
    """
    # スタイルの検証
    if style not in AVAILABLE_STYLES:
        logger.warning(f"指定されたスタイル '{style}' は無効です。利用可能なスタイル: {', '.join(AVAILABLE_STYLES)}。デフォルトの 'cyberpunk' を使用します。")
        style = "cyberpunk"
        
    input_data = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "style": style,
    }

    try:
        logger.debug(f"Calling FAL API with model: {MODEL_ID}")
        result = fal_client.submit(
            MODEL_ID,
            arguments=input_data,
            webhook_url=CALLBACK_URL + "/api/callback/generate/video"
        )
        logger.debug(f"Video generation completed successfully. Result: {result}")
        
#2025-05-03 12:01:29,504 - modules.video.generator - DEBUG - Video generation completed successfully. Result: SyncRequestHandle(request_id='63d92984-cdf2-4908-821f-da5a9a0012c6')
        
        # レスポンスをシリアライズ可能な形式に変換
        return {
            "success": True,
            "request_id": str(result.request_id),
            "status": "processing",
            "message": "Video generation started successfully"
        }

    except Exception as e:
        logger.debug(f"Calling error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred"
        }

def merge_video_audio(
    video_url: str,
    audio_url: str,
) -> dict:
    """
    動画と音声をマージする

    :param video_url: 動画のURL
    :param audio_url: 音声のURL
    """
    # URLをベースにした一貫性のあるハッシュを生成
    combined_urls = f"{video_url}|{audio_url}"
    file_id = hashlib.md5(combined_urls.encode()).hexdigest()[:12]  # 12文字のハッシュを使用
    
    temp_audio_path = f"{file_id}_audio.mp3"
    temp_video_path = f"{file_id}_video.mp4"
    output_path = f"{file_id}.mp4"

    try:
        # 音声ファイルをダウンロード
        audio_response = requests.get(audio_url)
        audio_response.raise_for_status()

        # 動画
        video_response = requests.get(video_url)
        video_response.raise_for_status()   

        # 一時ファイルを作成
        with open(temp_audio_path, 'wb') as f:
            f.write(audio_response.content)
        with open(temp_video_path, 'wb') as f:
            f.write(video_response.content)

        # 入力ファイル
        video = ffmpeg.input(temp_video_path)
        
        # 動画の長さを取得
        video_probe = ffmpeg.probe(temp_video_path)
        video_duration = float(video_probe['format']['duration'])
        
        # 音声の長さを取得
        audio_probe = ffmpeg.probe(temp_audio_path)
        audio_duration = float(audio_probe['format']['duration'])
        
        # ランダムな開始位置を計算（音声の長さから動画の長さを引いた範囲内）
        max_start_time = audio_duration - video_duration
        if max_start_time < 0:
            max_start_time = 0
        audio_start_time = random.uniform(0, max_start_time)
        
        print(f"Video duration: {video_duration} seconds")
        print(f"Audio duration: {audio_duration} seconds")
        print(f"Using audio from {audio_start_time:.2f} seconds")
        
        # 音声を動画の長さに合わせる（開始位置を指定）
        audio = ffmpeg.input(temp_audio_path, ss=audio_start_time, t=video_duration)

        # 動画と音声を結合
        stream = ffmpeg.output(
            video,
            audio,
            output_path,
            vcodec='copy',
            acodec='aac'
        )

        # 実行
        ffmpeg.run(stream, overwrite_output=True)

        print("Video and audio merged successfully!")

        # S3にアップロード
        bucket_name = os.getenv('S3_BUCKET')
        if not bucket_name:
            raise ValueError("S3_BUCKET environment variable is not set")
        
        s3_url = upload_to_s3(output_path, bucket_name)
        # s3_url = f"https://{bucket_name}.s3.amazonaws.com/generate/{output_path}"
        if not s3_url:
            raise Exception("Failed to upload to S3")

        # 一時ファイルを削除
        try:
            os.remove(temp_audio_path)
            os.remove(temp_video_path)
            os.remove(output_path)
            print(f"Temporary files removed: {temp_audio_path}, {temp_video_path}, {output_path}")
        except Exception as e:
            print(f"Warning: Failed to remove temporary files: {e}")

        return {
            "success": True,
            "message": "Video and audio merged successfully",
            "s3_url": s3_url
        }

    except requests.exceptions.RequestException as e:
        # エラー時も一時ファイルを削除
        try:
            os.remove(temp_audio_path)
            os.remove(temp_video_path)
            os.remove(output_path)
        except:
            pass
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to merge video and audio"
        }
    except Exception as e:
        # エラー時も一時ファイルを削除
        try:
            os.remove(temp_audio_path)
            os.remove(temp_video_path)
            os.remove(output_path)
        except:
            pass
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred"
        } 
    
def upload_to_s3(file_path, bucket_name):
    try:
        s3_client = boto3.client('s3')
        file_name = f"generated/{file_path}"
        
        s3_client.upload_file(
            file_path,
            bucket_name,
            file_name,
            ExtraArgs={'ContentType': 'video/mp4'}
        )
        
        # S3のURLを生成
        url = f"https://{bucket_name}.s3.amazonaws.com/{file_name}"
        print(f"File uploaded successfully to {url}")
        return url
    except ClientError as e:
        print(f"Error uploading to S3: {e}")
        return None