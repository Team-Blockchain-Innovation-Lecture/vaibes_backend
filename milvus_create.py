import time
import torch
import numpy as np
from transformers import BertJapaneseTokenizer, BertModel
from pymilvus import MilvusClient, DataType

# --- ① ハードコードされた音楽ジャンルとreference_urlのデータ ---
music_data = [
    {"genre": "rock", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Rex+Banner+-+Take+U+There+-+Instrumental+Version.mp3"},
    {"genre": "pop", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Wake+the+Wild+-+Press+Play.mp3"},
    {"genre": "classic", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Jean-Miles+Carter+-+Morning+Lilly.mp3"},
    {"genre": "jazz", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Semo+-+The+Microwave+Dance.mp3"},
    {"genre": "hiphop", "reference_url": "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Mo%CC%88nt+Lee+-+Dripper+-+No+Lead+Vocals.mp3"},
    # {"ジャンル": "R&B", "reference_url": "https://example.com/rnb_sample.mp3"},
    {"genre": "electronic", "reference_url": "https://tand-dev.github.io/audio-hosting/spinning-head-271171.mp3"},
    # {"ジャンル": "ダンス", "reference_url": "https://example.com/dance_sample.mp3"},
    # {"ジャンル": "レゲエ", "reference_url": "https://example.com/reggae_sample.mp3"},
    # {"ジャンル": "カントリー", "reference_url": "https://example.com/country_sample.mp3"},
    # {"ジャンル": "フォーク", "reference_url": "https://example.com/folk_sample.mp3"},
    # {"ジャンル": "ブルース", "reference_url": "https://example.com/blues_sample.mp3"},
    # {"ジャンル": "メタル", "reference_url": "https://example.com/metal_sample.mp3"},
    # {"ジャンル": "パンク", "reference_url": "https://example.com/punk_sample.mp3"},
    # {"ジャンル": "アンビエント", "reference_url": "https://example.com/ambient_sample.mp3"},
    # {"ジャンル": "ファンク", "reference_url": "https://example.com/funk_sample.mp3"},
    # {"ジャンル": "ソウル", "reference_url": "https://example.com/soul_sample.mp3"},
    # {"ジャンル": "ディスコ", "reference_url": "https://example.com/disco_sample.mp3"},
    # {"ジャンル": "テクノ", "reference_url": "https://example.com/techno_sample.mp3"},
    # {"ジャンル": "ハウス", "reference_url": "https://example.com/house_sample.mp3"},
    # {"ジャンル": "トランス", "reference_url": "https://example.com/trance_sample.mp3"},
    # {"ジャンル": "ドラムンベース", "reference_url": "https://example.com/drumandbass_sample.mp3"},
    # {"ジャンル": "ダブステップ", "reference_url": "https://example.com/dubstep_sample.mp3"},
    # {"ジャンル": "インディーロック", "reference_url": "https://example.com/indierock_sample.mp3"},
    # {"ジャンル": "オルタナティブロック", "reference_url": "https://example.com/alternativerock_sample.mp3"},
    # {"ジャンル": "ヘビーメタル", "reference_url": "https://example.com/heavymetal_sample.mp3"},
    # {"ジャンル": "デスメタル", "reference_url": "https://example.com/deathmetal_sample.mp3"},
    # {"ジャンル": "ブラックメタル", "reference_url": "https://example.com/blackmetal_sample.mp3"},
    # {"ジャンル": "ゴシックメタル", "reference_url": "https://example.com/gothicmetal_sample.mp3"},
    # {"ジャンル": "シンフォニックメタル", "reference_url": "https://example.com/symphonicmetal_sample.mp3"},
    # {"ジャンル": "ニューエイジ", "reference_url": "https://example.com/newage_sample.mp3"},
    # {"ジャンル": "ワールドミュージック", "reference_url": "https://example.com/worldmusic_sample.mp3"},
    # {"ジャンル": "ラテン", "reference_url": "https://example.com/latin_sample.mp3"},
    # {"ジャンル": "ボサノバ", "reference_url": "https://example.com/bossanova_sample.mp3"},
    # {"ジャンル": "サンバ", "reference_url": "https://example.com/samba_sample.mp3"},
    # {"ジャンル": "フラメンコ", "reference_url": "https://example.com/flamenco_sample.mp3"},
    # {"ジャンル": "アカペラ", "reference_url": "https://example.com/acapella_sample.mp3"},
    # {"ジャンル": "バロック", "reference_url": "https://example.com/baroque_sample.mp3"},
    # {"ジャンル": "ロマンティック", "reference_url": "https://example.com/romantic_sample.mp3"},
    # {"ジャンル": "オペラ", "reference_url": "https://example.com/opera_sample.mp3"}
]

# 各カラムのリスト作成
csv_ids = []
genres = []
reference_urls = []

for idx, item in enumerate(music_data):
    csv_ids.append(idx)
    genres.append(item["genre"])
    reference_urls.append(item["reference_url"])

print(f"データを準備しました。件数: {len(csv_ids)}")

# --- ② BERT によるテキストエンコード（ジャンル列のみ） ---
model_name = "tohoku-nlp/bert-base-japanese-v3"
tokenizer = BertJapaneseTokenizer.from_pretrained(model_name)
model = BertModel.from_pretrained(model_name)
model.eval()

def get_embedding(text):
    if not text:
        text = ""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
    # [CLS] トークンのベクトルを取得し、正規化（cosine類似度として内積で比較可能に）
    cls_vector = outputs.last_hidden_state[:, 0, :]
    vec = cls_vector.squeeze().numpy()
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm > 0 else vec.tolist()

embeddings = [get_embedding(text) for text in genres]
print("BERT によるエンコードが完了しました。")

# --- ③ Zilliz Cloud (Milvus SaaS) への登録 ---
# Zilliz Cloud の接続情報（管理コンソールで取得した URI と Token に置き換えてください）
milvus_uri = os.getenv("MILVUS_URI")
token = os.getenv("MILVUS_TOKEN")

# MilvusClient の生成（SaaS版の場合、secure接続となります）
milvus_client = MilvusClient(uri=milvus_uri, token=token)
print(f"Connected to Milvus at: {milvus_uri}")

# コレクション名の指定
collection_name = "music_genres"

# 既存のコレクションが存在する場合は削除
if milvus_client.has_collection(collection_name):
    milvus_client.drop_collection(collection_name)
    print(f"既存のコレクション {collection_name} を削除しました。")

# embeddingの次元数（BERT の出力次元）
dim = 768

# --- コレクション用スキーマの定義 ---
# MilvusClient の新APIでは create_schema() でスキーマオブジェクトを作成し、各フィールドを追加します
schema = milvus_client.create_schema()
schema.add_field("id", DataType.INT64, is_primary=True, auto_id=False, description="Unique identifier")
schema.add_field("genre", DataType.VARCHAR, max_length=255, description="音楽ジャンル")
schema.add_field("reference_url", DataType.VARCHAR, max_length=1024, description="参照URL")
schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim, description="BERTエンコードによる埋め込み")

# インデックス作成用パラメータの準備（ここではIVF_FLAT、内積(IP)を指定）
index_params = milvus_client.prepare_index_params()
index_params.add_index("embedding", metric_type="IP", index_type="IVF_FLAT", params={"nlist": 128})

# コレクション作成（作成時にスキーマ・インデックスパラメータを指定し、自動でロード）
milvus_client.create_collection(collection_name, schema=schema, index_params=index_params)
print(f"コレクション {collection_name} を作成しました。")

# --- データの挿入 ---
# 各レコードを辞書形式にまとめたリストを作成
records = []
for rec in zip(csv_ids, genres, reference_urls, embeddings):
    record = {
        "id": rec[0],
        "genre": rec[1],
        "reference_url": rec[2],
        "embedding": rec[3],
    }
    records.append(record)

t0 = time.time()
insert_result = milvus_client.insert(collection_name, records)
t1 = time.time()

# 新しいPyMilvusバージョンに対応
if hasattr(insert_result, 'primary_keys'):
    # 古いバージョン用
    inserted_count = len(insert_result.primary_keys)
elif isinstance(insert_result, dict) and 'insert_count' in insert_result:
    # 新しいバージョン用
    inserted_count = insert_result['insert_count']
else:
    # その他のケース
    inserted_count = "不明"

print(f"Milvus へのデータ挿入が完了しました。挿入件数: {inserted_count} (所要時間: {round(t1-t0,4)}秒)")

# 挿入後、flush で永続化（クラウド版の場合も明示的なflushを実施するのが望ましい）
print("Flushing collection...")
t0 = time.time()
milvus_client.flush(collection_name)
t1 = time.time()
print(f"Flush 完了 (所要時間: {round(t1-t0,4)}秒)")

# インデックスの作成（create_collection 時にインデックスパラメータを指定している場合は自動作成されます）
print("Creating index...")
t0 = time.time()
milvus_client.create_index(collection_name, field_name="embedding", index_params=index_params)
t1 = time.time()
print(f"インデックス作成完了 (所要時間: {round(t1-t0,4)}秒)")

# コレクションをロード（検索可能な状態にする）
print("Loading collection...")
t0 = time.time()
milvus_client.load_collection(collection_name)
t1 = time.time()
print(f"コレクションロード完了 (所要時間: {round(t1-t0,4)}秒)")

# 簡単な検索テスト
test_queries = ["ロック", "エレクトロニック", "クラシック", "ヒップホップとR&B", "アンビエント系の落ち着いた音楽"]
for test_query in test_queries:
    test_embedding = get_embedding(test_query)
    search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
    results = milvus_client.search(
        collection_name=collection_name,
        data=[test_embedding],
        field_name="embedding",
        limit=3,
        search_params=search_params,
        output_fields=["genre", "reference_url"]
    )

    print("\n検索テスト:")
    print(f"クエリ: '{test_query}'")
    print("検索結果:")
    for i, result in enumerate(results[0]):
        print(f"  {i+1}. スコア: {result.score:.4f}, ジャンル: {result.entity.get('genre')}, URL: {result.entity.get('reference_url')}")

print("\nMilvusデータベースの作成が完了しました。")
