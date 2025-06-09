import os
import fal_client
from typing import Optional, Dict, Any

class Veo3Client:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FAL_KEY")
        if not self.api_key:
            raise ValueError("FAL_KEY environment variable or api_key parameter is required")
        
        # FALクライアントの設定
        os.environ["FAL_KEY"] = self.api_key

    def generate_video(self, 
                      prompt: str,
                      aspect_ratio: str = "9:16",
                      duration: str = "8s",
                      enhance_prompt: bool = True,
                      generate_audio: bool = True,
                      negative_prompt: Optional[str] = None,
                      seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Veo3を使用して動画を生成します。

        Args:
            prompt (str): 動画生成のためのプロンプト
            aspect_ratio (str): アスペクト比 ("16:9", "9:16", "1:1")
            duration (str): 動画の長さ
            enhance_prompt (bool): プロンプトの強化を行うかどうか
            generate_audio (bool): 音声を生成するかどうか
            negative_prompt (Optional[str]): ネガティブプロンプト
            seed (Optional[int]): シード値

        Returns:
            Dict[str, Any]: 生成された動画の情報
        """
        try:
            # キュー更新のコールバック関数
            def on_queue_update(update):
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(log["message"])

            # リクエストの引数を準備
            arguments = {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "enhance_prompt": enhance_prompt,
                "generate_audio": generate_audio
            }

            if negative_prompt:
                arguments["negative_prompt"] = negative_prompt
            if seed is not None:
                arguments["seed"] = seed

            # 動画生成リクエストを送信
            result = fal_client.subscribe(
                "fal-ai/veo3",
                arguments=arguments,
                with_logs=True,
                on_queue_update=on_queue_update
            )

            return result

        except Exception as e:
            raise Exception(f"FAL API request failed: {str(e)}")