# 1st code block
import requests
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# APIキーを取得
AIML_API_KEY = os.environ.get("AIML_API_KEY")
if not AIML_API_KEY:
    print("エラー: AIML_API_KEYが環境変数に設定されていません")
    exit(1)

def main():
    url = "https://api.aimlapi.com/v2/generate/audio"
    payload = {
        "model": "minimax-music",
        "reference_audio_url": 'https://tand-dev.github.io/audio-hosting/spinning-head-271171.mp3',
        "prompt": '''
##Side by side, through thick and thin, \n\nWith a laugh, we always win. \n\n Storms may come, but we stay true, \n\nFriends forever—me and you!##
''',   
    }
    
    headers = {"Authorization": f"Bearer {AIML_API_KEY}", "Content-Type": "application/json"}
    
    print(f"APIキーの先頭部分: {AIML_API_KEY[:10]}...")
    
    response = requests.post(url, json=payload, headers=headers)
    print(f"ステータスコード: {response.status_code}")
    print("レスポンス:", response.json())


if __name__ == "__main__":
    main()
