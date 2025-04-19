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

```
curl -X POST "https://b94d-203-136-72-13.ngrok-free.app/api/generate-with-callback" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "クールなEDMで「バイブス」と歌って",
    "genre": "EDM",
    "instrumental": false,
    "model_version": "v4",
    "timeout": 60
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
export CALLBACK_URL=https://bc73-122-222-70-231.ngrok-free.app/callback
```


