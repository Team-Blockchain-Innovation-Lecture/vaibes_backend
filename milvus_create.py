import os
import time
import torch
import numpy as np
from transformers import BertTokenizer, BertModel
from pymilvus import MilvusClient, DataType
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- ① Hardcoded music genre and reference_url data ---
music_data = [
    {"genre": "rock", "description": "Energetic rock music", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Rex+Banner+-+Take+U+There+-+Instrumental+Version.mp3"},
    {"genre": "pop", "description": "Catchy pop music", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Wake+the+Wild+-+Press+Play.mp3"},
    {"genre": "classic", "description": "Classical music", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Jean-Miles+Carter+-+Morning+Lilly.mp3"},
    {"genre": "jazz", "description": "Smooth jazz", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Semo+-+The+Microwave+Dance.mp3"},
    {"genre": "hiphop", "description": "Rhythmic hip-hop", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Mo%CC%88nt+Lee+-+Dripper+-+No+Lead+Vocals.mp3"},
    # {"genre": "R&B", "description": "Soulful R&B", "reference_url": "https://example.com/rnb_sample.mp3"},
    {"genre": "electronic", "description": "Electronic music", "reference_url": "https://tand-dev.github.io/audio-hosting/spinning-head-271171.mp3"},
    # {"genre": "dance", "description": "Dance music", "reference_url": "https://example.com/dance_sample.mp3"},
    # {"genre": "reggae", "description": "Reggae music", "reference_url": "https://example.com/reggae_sample.mp3"},
    # {"genre": "country", "description": "Country music", "reference_url": "https://example.com/country_sample.mp3"},
    # {"genre": "folk", "description": "Folk music", "reference_url": "https://example.com/folk_sample.mp3"},
    # {"genre": "blues", "description": "Blues music", "reference_url": "https://example.com/blues_sample.mp3"},
    # {"genre": "metal", "description": "Heavy metal", "reference_url": "https://example.com/metal_sample.mp3"},
    # {"genre": "punk", "description": "Punk rock", "reference_url": "https://example.com/punk_sample.mp3"},
    # {"genre": "ambient", "description": "Ambient music", "reference_url": "https://example.com/ambient_sample.mp3"},
    # {"genre": "funk", "description": "Funky music", "reference_url": "https://example.com/funk_sample.mp3"},
    # {"genre": "soul", "description": "Soul music", "reference_url": "https://example.com/soul_sample.mp3"},
    # {"genre": "disco", "description": "Disco music", "reference_url": "https://example.com/disco_sample.mp3"},
    # {"genre": "techno", "description": "Techno music", "reference_url": "https://example.com/techno_sample.mp3"},
    # {"genre": "house", "description": "House music", "reference_url": "https://example.com/house_sample.mp3"},
    # {"genre": "trance", "description": "Trance music", "reference_url": "https://example.com/trance_sample.mp3"},
    # {"genre": "drum and bass", "description": "Drum and bass", "reference_url": "https://example.com/drumandbass_sample.mp3"},
    # {"genre": "dubstep", "description": "Dubstep", "reference_url": "https://example.com/dubstep_sample.mp3"},
    # {"genre": "indie rock", "description": "Indie rock", "reference_url": "https://example.com/indierock_sample.mp3"},
    # {"genre": "alternative rock", "description": "Alternative rock", "reference_url": "https://example.com/alternativerock_sample.mp3"},
    # {"genre": "heavy metal", "description": "Heavy metal", "reference_url": "https://example.com/heavymetal_sample.mp3"},
    # {"genre": "death metal", "description": "Death metal", "reference_url": "https://example.com/deathmetal_sample.mp3"},
    # {"genre": "black metal", "description": "Black metal", "reference_url": "https://example.com/blackmetal_sample.mp3"},
    # {"genre": "gothic metal", "description": "Gothic metal", "reference_url": "https://example.com/gothicmetal_sample.mp3"},
    # {"genre": "symphonic metal", "description": "Symphonic metal", "reference_url": "https://example.com/symphonicmetal_sample.mp3"},
    # {"genre": "new age", "description": "New age music", "reference_url": "https://example.com/newage_sample.mp3"},
    # {"genre": "world music", "description": "World music", "reference_url": "https://example.com/worldmusic_sample.mp3"},
    # {"genre": "latin", "description": "Latin music", "reference_url": "https://example.com/latin_sample.mp3"},
    # {"genre": "bossa nova", "description": "Bossa nova", "reference_url": "https://example.com/bossanova_sample.mp3"},
    # {"genre": "samba", "description": "Samba", "reference_url": "https://example.com/samba_sample.mp3"},
    # {"genre": "flamenco", "description": "Flamenco", "reference_url": "https://example.com/flamenco_sample.mp3"},
    # {"genre": "acapella", "description": "Acapella", "reference_url": "https://example.com/acapella_sample.mp3"},
    # {"genre": "baroque", "description": "Baroque music", "reference_url": "https://example.com/baroque_sample.mp3"},
    # {"genre": "romantic", "description": "Romantic music", "reference_url": "https://example.com/romantic_sample.mp3"},
    # {"genre": "opera", "description": "Opera", "reference_url": "https://example.com/opera_sample.mp3"}
]

# Create lists for each column
csv_ids = []
genres = []
descriptions = []
reference_urls = []

for idx, item in enumerate(music_data):
    csv_ids.append(idx)
    genres.append(item["genre"])
    descriptions.append(item["description"])
    reference_urls.append(item["reference_url"])

print(f"Data prepared. Count: {len(csv_ids)}")

# --- ② BERT text encoding (for genre and description) ---
model_name = "bert-base-uncased"  # Changed to English BERT model
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertModel.from_pretrained(model_name)
model.eval()

def get_embedding(text):
    if not text:
        text = ""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    # Get the [CLS] token vector and normalize (for cosine similarity comparison)
    cls_vector = outputs.last_hidden_state[:, 0, :]
    vec = cls_vector.squeeze().numpy()
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm > 0 else vec.tolist()

# Combine genre and description for encoding
combined_texts = [f"{genre} {desc}" for genre, desc in zip(genres, descriptions)]
embeddings = [get_embedding(text) for text in combined_texts]
print("BERT encoding completed.")

# --- ③ Register to Zilliz Cloud (Milvus SaaS) ---
# Zilliz Cloud connection info (replace with URI and Token from management console)

milvus_uri = ""
token = ""

# Create MilvusClient (secure connection for SaaS version)
milvus_client = MilvusClient(uri=milvus_uri, token=token)
print(f"Connected to Milvus at: {milvus_uri}")

# Specify collection name
collection_name = "vaibes_music"

# Delete existing collection if it exists
if milvus_client.has_collection(collection_name):
    milvus_client.drop_collection(collection_name)
    print(f"Deleted existing collection {collection_name}.")

# Embedding dimension (BERT output dimension)
dim = 768

# --- Define collection schema ---
# In the new MilvusClient API, create_schema() creates a schema object and adds fields
schema = milvus_client.create_schema()
schema.add_field("id", DataType.INT64, is_primary=True, auto_id=False, description="Unique identifier")
schema.add_field("genre", DataType.VARCHAR, max_length=255, description="Music genre")
schema.add_field("description", DataType.VARCHAR, max_length=1024, description="Genre description")
schema.add_field("reference_url", DataType.VARCHAR, max_length=1024, description="Reference URL")
schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim, description="BERT encoded embedding")

# Prepare index creation parameters (here we specify IVF_FLAT, inner product (IP))
index_params = milvus_client.prepare_index_params()
index_params.add_index("embedding", metric_type="IP", index_type="IVF_FLAT", params={"nlist": 128})

# Create collection (specify schema and index parameters at creation, auto-load)
milvus_client.create_collection(collection_name, schema=schema, index_params=index_params)
print(f"Created collection {collection_name}.")

# --- Insert data ---
# Create a list of records in dictionary format
records = []
for rec in zip(csv_ids, genres, descriptions, reference_urls, embeddings):
    record = {
        "id": rec[0],
        "genre": rec[1],
        "description": rec[2],
        "reference_url": rec[3],
        "embedding": rec[4],
    }
    records.append(record)

t0 = time.time()
insert_result = milvus_client.insert(collection_name, records)
t1 = time.time()

# Handle different PyMilvus versions
if hasattr(insert_result, 'primary_keys'):
    # For older version
    inserted_count = len(insert_result.primary_keys)
elif isinstance(insert_result, dict) and 'insert_count' in insert_result:
    # For newer version
    inserted_count = insert_result['insert_count']
else:
    # For other cases
    inserted_count = "unknown"

print(f"Data insertion to Milvus completed. Inserted count: {inserted_count} (time: {round(t1-t0,4)} seconds)")

# Flush after insertion (explicit flush is recommended even for cloud version)
print("Flushing collection...")
t0 = time.time()
milvus_client.flush(collection_name)
t1 = time.time()
print(f"Flush completed (time: {round(t1-t0,4)} seconds)")

# Create index (automatically created if index parameters are specified at collection creation)
print("Creating index...")
t0 = time.time()
milvus_client.create_index(collection_name, field_name="embedding", index_params=index_params)
t1 = time.time()
print(f"Index creation completed (time: {round(t1-t0,4)} seconds)")

# Load collection (make it searchable)
print("Loading collection...")
t0 = time.time()
milvus_client.load_collection(collection_name)
t1 = time.time()
print(f"Collection loading completed (time: {round(t1-t0,4)} seconds)")

# Simple search test
test_queries = ["Rock", "Electronic", "Classical", "Hip-hop and R&B", "Ambient relaxing music"]
for test_query in test_queries:
    test_embedding = get_embedding(test_query)
    search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
    results = milvus_client.search(
        collection_name=collection_name,
        data=[test_embedding],
        field_name="embedding",
        limit=3,
        search_params=search_params,
        output_fields=["genre", "description", "reference_url"]
    )

    print("\nSearch test:")
    print(f"Query: '{test_query}'")
    print("Search results:")
    for i, result in enumerate(results[0]):
        print(f"  {i+1}. Score: {result.score:.4f}, Genre: {result.entity.get('genre')}, Description: {result.entity.get('description')}, URL: {result.entity.get('reference_url')}")

print("\nMilvus database creation completed.")
