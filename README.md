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
    "prompt": "すごくクールなEDMを生成して",
    "genre": "EDM",
    "instrumental": true,
    "model_version": "v3.5"
  }'
```