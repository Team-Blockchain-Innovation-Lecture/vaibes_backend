# vaibes_backend

## Setup（poetry）

```bash
poetry install
```

## Run

```bash
poetry run python XXX.py
または
poetry run python -m XXX
```

## Milvus

```bash
poetry run python milvus_create.py
```

## テスト

```bash
curl -X POST "http://localhost:5001/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "クールなEDMで「バイブス」と歌って",
    "genre": "EDM",
    "instrumental": false,
    "model_version": "v3.5"
  }'
```

### コールバック含めた音楽生成
```
curl -X POST "https://5fe5-240b-10-27c1-7e00-1c55-e4aa-22e4-d0cd.ngrok-free.app/api/generate-with-callback" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Silk‑lined shadows weave across the boulevard,Reflections dancing on a midnight silver car.",
    "genre": "EDM",
    "instrumental": false,
    "model_version": "v4",
    "timeout": 5
  }'
```

### 動画生成
```
curl -X POST "https://b94d-203-136-72-13.ngrok-free.app/api/generate-mp4-with-callback" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "0e471d75a5ad51c7d1675ab54b020f3c",
    "audio_id": "5cf62da6-b180-4df2-af98-eec3a7d14b5d",
    "author" : "Omatsu"
  }'
```
ngrokをインストール
```bash
brew install ngrok
```
ngrokのAPIキーを設定
```bash
ngrok config add-authtoken <ngrokのAPIキー>
```

ngrokを起動
```bash
ngrok http 5001
```

ngrokのURLを環境変数に設定
```bash
export CALLBACK_URL=https://ae73-240b-10-27c1-7e00-2425-9b44-c411-f7a7.ngrok-free.app/callback
```


