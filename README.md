# vaibes_backend
## Setup (python)
```bash
brew install python@3.11
```
### install poetry
```
curl -sSL https://install.python-poetry.org | python3.11 -
```

## Setup (poetry)

```bash
poetry env use python3.11
```

```bash
poetry install
```

## Run

```bash
poetry run python XXX.py
or
poetry run python -m XXX
```

## Milvus

```bash
poetry run python milvus_create.py
```

## Testing

```bash
curl -X POST "http://localhost:5001/api/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Cool EDM with lyrics saying 'Vibes'",
    "genre": "EDM",
    "instrumental": false,
    "model_version": "v3.5"
  }'
```

### Music Generation with Callback
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

### Video Generation
```
curl -X POST "https://b94d-203-136-72-13.ngrok-free.app/api/generate-mp4-with-callback" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "0e471d75a5ad51c7d1675ab54b020f3c",
    "audio_id": "5cf62da6-b180-4df2-af98-eec3a7d14b5d",
    "author" : "Omatsu"
  }'
```

## ngrok Setup

Install ngrok
```bash
brew install ngrok
```

Configure ngrok API key
```bash
ngrok config add-authtoken <your-ngrok-api-key>
```

Start ngrok
```bash
ngrok http 5001
```

Set ngrok URL as environment variable
```bash
export CALLBACK_URL=https://ae73-240b-10-27c1-7e00-2425-9b44-c411-f7a7.ngrok-free.app/callback
```


