import os
import time
import json
import requests
import numpy as np
import torch
from flask import Flask, request, jsonify, send_file
from transformers import BertJapaneseTokenizer, BertModel, BertTokenizer
from pymilvus import MilvusClient
import uuid
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Flaskアプリケーションの初期化
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 日本語などの非ASCII文字をエスケープしない
load_dotenv(dotenv_path=".env")

# Milvus接続設定
MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION")

# AIML API設定
AIML_API_KEY = os.getenv("AIML_API_KEY")

# デフォルトのプロンプト
DEFAULT_PROMPT = "ジャズとクラシックが融合した落ち着いた雰囲気の曲"

# 出力ディレクトリの設定
OUTPUT_DIR = "downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# BERTモデルの初期化 - 英語モデルに変更
print("Initializing BERT model...")
model_name = "bert-base-uncased"  # 英語BERTモデルを使用
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertModel.from_pretrained(model_name)
model.eval()
print("BERT model initialization completed")

# Milvusクライアントの初期化
print(f"Milvusに接続中... ({MILVUS_URI})")
milvus_client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
print("Milvus接続完了")

# テキストからベクトルを取得する関数 - 英語モデル用に修正
def get_embedding(text):
    if not text:
        text = ""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    # [CLS] トークンのベクトルを取得し、正規化
    cls_vector = outputs.last_hidden_state[:, 0, :]
    vec = cls_vector.squeeze().numpy()
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm > 0 else vec.tolist()

# Milvusから参照URLを取得する関数 - 完全修正版
def get_reference_url_from_milvus(text, genre=None):
    try:
        # Milvusが利用できない場合はデフォルトの参照URLを返す
        if milvus_client is None:
            print("Milvus client is not available. Using default reference URL")
            default_url = "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Rex+Banner+-+Take+U+There+-+Instrumental+Version.mp3"
            return default_url, "rock", "Energetic rock music"
            
        print(f"Vectorizing text: '{text}'...")
        embedding = get_embedding(text)
        print("Vectorization completed")
        
        print("Searching for similar genres in Milvus...")
        
        # ジャンルフィルタの設定
        expr = None
        if genre:
            expr = f'genre == "{genre}"'
            print(f"Genre filter: {expr}")
        
        # 検索実行 - 修正: 以前の動作していたコードを参考に実装
        try:
            # 最初の試行: search_paramsを使用
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            results = milvus_client.search(
                collection_name=MILVUS_COLLECTION,
                data=[embedding],
                anns_field="embedding",  # field_nameではなくanns_fieldを使用
                search_params=search_params,  # search_paramsを使用
                limit=3,
                expr=expr,
                output_fields=["genre", "description", "reference_url"]
            )
        except Exception as e1:
            print(f"First search attempt failed: {e1}")
            try:
                # 2番目の試行: paramを使用
                search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
                results = milvus_client.search(
                    collection_name=MILVUS_COLLECTION,
                    data=[embedding],
                    anns_field="embedding",
                    param=search_params,  # paramを使用
                    limit=3,
                    expr=expr,
                    output_fields=["genre", "description", "reference_url"]
                )
            except Exception as e2:
                print(f"Second search attempt failed: {e2}")
                # 3番目の試行: field_nameを使用
                search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
                results = milvus_client.search(
                    collection_name=MILVUS_COLLECTION,
                    data=[embedding],
                    field_name="embedding",  # anns_fieldではなくfield_nameを使用
                    search_params=search_params,
                    limit=3,
                    expr=expr,
                    output_fields=["genre", "description", "reference_url"]
                )
        
        print(f"Search results: {results}")
        
        # 検索結果を処理
        search_results = []
        top_reference_url = None
        top_genre = None
        top_description = None
        
        if results and len(results) > 0 and len(results[0]) > 0:
            for i, hit in enumerate(results[0]):
                print(f"Hit {i+1} type: {type(hit)}")
                print(f"Hit {i+1} content: {hit}")
                
                # 結果の構造に応じて処理
                hit_genre = None
                hit_reference_url = None
                hit_description = None
                hit_score = 0
                
                # entityがある場合
                if hasattr(hit, 'entity'):
                    entity = hit.entity
                    if isinstance(entity, dict):
                        hit_genre = entity.get('genre')
                        hit_reference_url = entity.get('reference_url')
                        hit_description = entity.get('description')
                    else:
                        # entityがオブジェクトの場合
                        hit_genre = getattr(entity, 'genre', None)
                        hit_reference_url = getattr(entity, 'reference_url', None)
                        hit_description = getattr(entity, 'description', None)
                    
                    hit_score = getattr(hit, 'score', getattr(hit, 'distance', 0))
                # 辞書型の場合
                elif isinstance(hit, dict):
                    hit_genre = hit.get('genre')
                    hit_reference_url = hit.get('reference_url')
                    hit_description = hit.get('description')
                    hit_score = hit.get('score', hit.get('distance', 0))
                
                print(f"  {i+1}. Genre: {hit_genre}, Score: {hit_score}")
                print(f"     Description: {hit_description}")
                print(f"     Reference URL: {hit_reference_url}")
                
                # 検索結果をリストに追加
                if hit_genre or hit_reference_url or hit_description:
                    search_results.append({
                        "genre": hit_genre,
                        "reference_url": hit_reference_url,
                        "description": hit_description,
                        "score": float(hit_score) if hit_score else 0.0
                    })
                
                # 最初のヒットを参照URLとして使用
                if i == 0:
                    top_reference_url = hit_reference_url
                    top_genre = hit_genre
                    top_description = hit_description
        
        # 検索結果がない場合はデフォルト値を使用
        if not top_reference_url:
            print("No search results found. Using default values")
            top_reference_url = "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Rex+Banner+-+Take+U+There+-+Instrumental+Version.mp3"
            top_genre = "rock"
            top_description = "Energetic rock music"
        
        print(f"Selected reference URL: {top_reference_url}")
        print(f"Selected genre: {top_genre}")
        print(f"Selected description: {top_description}")
        
        return top_reference_url, top_genre, top_description
        
    except Exception as e:
        print(f"Milvus search error: {str(e)}")
        print("Using default reference URL")
        import traceback
        traceback.print_exc()
        return "https://vaibes-prd-s3-music.s3.ap-northeast-1.amazonaws.com/refarence_music/Rex+Banner+-+Take+U+There+-+Instrumental+Version.mp3", "rock", "Energetic rock music"

# AIMLを使用して音楽を生成する関数
def generate_music(prompt, reference_url=None):
    try:
        print("\n音楽生成を開始します...")
        
        # 参照URLが指定されていない場合は、Milvusから取得を試みる
        if not reference_url:
            print("参照URLが指定されていないため、Milvusから検索します...")
            reference_url, genre, description = get_reference_url_from_milvus(prompt)
            if reference_url:
                print(f"Milvusから参照URLを取得しました: {reference_url}")
                print(f"ジャンル: {genre}")
            else:
                print("Milvusから参照URLを取得できませんでした。デフォルトURLを使用します。")
                # デフォルトの参照URL（実際のプロジェクトでは適切なURLに置き換えてください）
                reference_url = "https://example.com/sample.mp3"
        
        # 音楽生成APIのエンドポイント
        url = "https://api.aimlapi.com/v2/generate/audio"
        
        # リクエストデータの準備
        payload = {
            "model": "minimax-music",
            "prompt": prompt,
            "reference_audio_url": reference_url,
            "min_duration": 120,
            "output_format": "mp3",
            "temperature": 0.5,
            "top_p": 0.9,
        }
        
        # APIリクエストヘッダー
        headers = {
            "Authorization": f"Bearer {AIML_API_KEY}",
            "Content-Type": "application/json"
        }
        
        print("APIリクエスト送信中...")
        print(f"リクエストデータ: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, headers=headers)
        
        # レスポンスを確認
        print(f"APIレスポンス: ステータスコード={response.status_code}")
        print(f"レスポンス本文: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            generation_id = result.get("generation_id")
            print(f"生成ID: {generation_id}")
            return generation_id
        else:
            print(f"APIエラー: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"音楽生成エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# 音楽ファイルをダウンロードする関数 - test2.pyを参考に修正
def download_music(generation_id):
    try:
        print(f"\n音楽ファイルをダウンロード中（生成ID: {generation_id}）")
        
        # test2.pyと同様のリクエスト方法
        url = "https://api.aimlapi.com/v2/generate/audio"
        params = {
            "generation_id": generation_id
        }
        headers = {
            "Authorization": f"Bearer {AIML_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, params=params, headers=headers)
        print(f"ダウンロードレスポンス: ステータスコード={response.status_code}")
        
        if response.status_code == 200:
            # レスポンスからJSONデータを取得
            result = response.json()
            print(f"ダウンロードレスポンス: {json.dumps(result, ensure_ascii=False)}")
            
            # 音楽URLを取得
            audio_url = None
            if "audio_url" in result:
                audio_url = result.get("audio_url")
            elif "output" in result and "audio" in result.get("output", {}):
                audio_url = result.get("output", {}).get("audio")
            
            if not audio_url:
                print("音楽URLが見つかりません")
                return None, None
            
            print(f"音楽URL: {audio_url}")
            
            # ファイル名を生成（UUIDを使用して一意にする）
            filename = f"music_{uuid.uuid4()}.mp3"
            local_path = os.path.join(OUTPUT_DIR, filename)
            
            # 音楽URLからファイルをダウンロード
            audio_response = requests.get(audio_url, stream=True)
            if audio_response.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in audio_response.iter_content(chunk_size=8192):
                        if chunk:  # フィルタして空のチャンクをスキップ
                            f.write(chunk)
                print(f"ダウンロード完了: {local_path}")
                return local_path, filename
            else:
                print(f"音楽ファイルのダウンロードエラー: {audio_response.status_code} - {audio_response.text}")
                return None, None
        else:
            print(f"ダウンロードエラー: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"ダウンロードエラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

# 音楽生成状態を確認する関数 - 修正版
def check_generation_status(generation_id):
    try:
        print(f"\nChecking generation status...")
        
        # generation_idからモデル名を削除（:以降を削除）
        if ":" in generation_id:
            generation_id = generation_id.split(":")[0]
            print(f"Modified generation ID: {generation_id}")
        
        # AIML APIキーの確認
        if not AIML_API_KEY:
            print("ERROR: AIML_API_KEY is not set")
            return None
        
        # 最大試行回数
        max_attempts = 30
        
        for attempt in range(1, max_attempts + 1):
            print(f"Status check attempt {attempt}/{max_attempts}...")
            
            # 両方のエンドポイントを試す
            endpoints = [
                f"https://api.aimlapi.com/v2/generations/{generation_id}",  # 古いエンドポイント
                f"https://api.aimlapi.com/v2/generate/audio/{generation_id}"  # 新しいエンドポイント
            ]
            
            # APIリクエストヘッダー
            headers = {
                "Authorization": f"Bearer {AIML_API_KEY}",
                "Content-Type": "application/json"
            }
            
            success = False
            
            for endpoint in endpoints:
                print(f"Trying endpoint: {endpoint}")
                response = requests.get(endpoint, headers=headers)
                print(f"Status check response: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        print(f"Status details: {json.dumps(result, ensure_ascii=False)}")
                        
                        # ステータスを取得
                        status = result.get("status", "").lower()
                        
                        # 完了した場合
                        if status == "completed":
                            # 出力URLを取得
                            output_url = result.get("output_url")
                            if output_url:
                                print(f"Generation completed! Output URL: {output_url}")
                                return output_url
                            else:
                                print("ERROR: output_url not found in completed response")
                        # 失敗した場合
                        elif status in ["failed", "error"]:
                            error_message = result.get("error", "Unknown error")
                            print(f"Generation failed: {error_message}")
                        # まだ処理中の場合
                        else:
                            print(f"Current status: {status}. Waiting...")
                            success = True  # 有効なレスポンスを受け取った
                            break
                    except json.JSONDecodeError:
                        print(f"JSON parse error: {response.text}")
            
            # 有効なレスポンスを受け取った場合は待機
            if success:
                time.sleep(10)  # 10秒待機
                continue
            
            # どちらのエンドポイントも失敗した場合は待機して再試行
            print("Both endpoints failed. Retrying...")
            time.sleep(10)  # 10秒待機
        
        print(f"Maximum attempts ({max_attempts}) reached. Timeout.")
        return None
    
    except Exception as e:
        print(f"Error during status check: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# 音楽生成プロセス全体を実行する関数
def process_music_generation(prompt=None):
    try:
        # プロンプトが指定されていない場合はデフォルト値を使用
        if prompt is None or prompt.strip() == "":
            prompt = DEFAULT_PROMPT
            print(f"プロンプトが指定されていないため、デフォルト値を使用します: {prompt}")
        
        print(f"\n=== 音楽生成プロセスを開始 ===")
        print(f"プロンプト: {prompt}")
        
        # Milvusから参照URLを取得
        reference_url, genre, description = get_reference_url_from_milvus(prompt)
        
        if reference_url:
            print(f"\n最も類似したジャンル: {genre}")
            print(f"参照URL: {reference_url}")
        else:
            print("\n参照URLが見つかりませんでした。デフォルトを使用します。")
            # デフォルトの参照URL（実際のプロジェクトでは適切なURLに置き換えてください）
            reference_url = "https://example.com/sample.mp3"
        
        # 音楽生成
        generation_id = generate_music(prompt, reference_url)
        
        if not generation_id:
            error_msg = "音楽生成に失敗しました。APIレスポンスを確認してください。"
            print(error_msg)
            return {"error": error_msg}, None, None
        
        # 生成状態を確認
        output_url = check_generation_status(generation_id)
        
        if not output_url:
            error_msg = "音楽生成状態の確認に失敗しました。"
            print(error_msg)
            return {"error": error_msg}, None, None
        
        # 音楽ファイルをダウンロード
        local_file_path, filename = download_music(generation_id)
        
        if not local_file_path:
            error_msg = "音楽ファイルのダウンロードに失敗しました。"
            print(error_msg)
            return {"error": error_msg}, None, None
        
        print(f"\n=== 音楽生成プロセスが完了しました ===")
        print(f"ファイル: {local_file_path}")
        print(f"ジャンル: {genre}")
        
        return {
            "success": True,
            "message": "音楽生成が完了しました",
            "filename": filename,
            "genre": genre,
            "prompt": prompt,
            "reference_url": reference_url,
            "description": description
        }, local_file_path, filename
        
    except Exception as e:
        error_msg = f"処理エラー: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return {"error": error_msg}, None, None

# APIエンドポイント: 音楽を生成（プロンプトはクエリパラメータまたはJSONボディから取得）
@app.route('/api/generate', methods=['GET', 'POST'])
def api_generate():
    try:
        # プロンプトの取得（複数の方法をサポート）
        prompt = None
        
        # 1. GETリクエストのクエリパラメータから取得
        if request.method == 'GET':
            prompt = request.args.get('prompt')
        
        # 2. POSTリクエストのJSONボディから取得
        elif request.is_json:
            data = request.get_json()
            prompt = data.get('prompt')
        
        # 3. POSTリクエストのフォームデータから取得
        else:
            prompt = request.form.get('prompt')
        
        # プロンプトが指定されていない場合はデフォルト値を使用
        if not prompt:
            prompt = DEFAULT_PROMPT
            print(f"プロンプトが指定されていないため、デフォルト値を使用します: {prompt}")
        
        print(f"\n=== 音楽生成プロセスを開始 ===")
        print(f"プロンプト: {prompt}")
        
        # 1. Milvusから参照URLを取得
        print("\n1. Milvusから参照URLを取得中...")
        reference_url, genre, description = get_reference_url_from_milvus(prompt)
        
        if not reference_url:
            print("Milvusから参照URLを取得できませんでした。デフォルトURLを使用します。")
            reference_url = "https://example.com/sample.mp3"
            genre = "不明"
            description = "Unknown"
        else:
            print(f"Milvusから参照URLを取得しました: {reference_url}")
            print(f"ジャンル: {genre}")
        
        # 2. 音楽生成APIを呼び出し
        print("\n2. 音楽生成APIを呼び出し中...")
        url = "https://api.aimlapi.com/v2/generate/audio"
        
        headers = {
            "Authorization": f"Bearer {AIML_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "minimax-music",
            "prompt": prompt,
            "reference_audio_url": reference_url,
            "min_duration": 120,
            "output_format": "mp3",
            "temperature": 0.5,
            "top_p": 0.9,
        }
        
        print(f"リクエストデータ: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(url, json=payload, headers=headers)
        print(f"APIレスポンス: ステータスコード={response.status_code}")
        print(f"レスポンス本文: {response.text}")
        
        # 201（Created）または200（OK）を成功として扱う
        if response.status_code not in [200, 201]:
            error_msg = f"音楽生成APIエラー: {response.status_code} - {response.text}"
            print(error_msg)
            return app.response_class(
                response=json.dumps({"error": error_msg}, ensure_ascii=False),
                status=500,
                mimetype='application/json; charset=utf-8'
            )
        
        result = response.json()
        
        # レスポンスの形式に応じて生成IDを取得
        if "generation_id" in result:
            generation_id = result.get("generation_id")
        elif "id" in result:
            generation_id = result.get("id")
        else:
            # レスポンスの構造をログに出力
            print(f"レスポンス構造: {json.dumps(result, ensure_ascii=False, indent=2)}")
            # レスポンスの形式が予期しないものの場合、キーを探す
            for key, value in result.items():
                if isinstance(value, str) and ":" in value:
                    # ID形式の文字列を探す（例: "6269e347-199b-49d3-9a2c-416387e26963:stable-audio"）
                    generation_id = value
                    print(f"生成IDを抽出しました: {generation_id}")
                    break
            else:
                error_msg = "生成IDが見つかりません。レスポンス形式が予期しないものです。"
                print(error_msg)
                return app.response_class(
                    response=json.dumps({"error": error_msg, "response": result}, ensure_ascii=False),
                    status=500,
                    mimetype='application/json; charset=utf-8'
                )
        
        print(f"生成ID: {generation_id}")
        
        # 3. 生成が完了するまで待機（最大5分）
        print("\n3. 生成が完了するまで待機中...")
        
        # 最大30回（5分間）試行
        for attempt in range(1, 31):
            print(f"待機中... 試行 {attempt}/30")
            # 10秒待機
            time.sleep(10)
            
            # 4. 音楽ファイルの生成状態を確認
            print(f"\n4. 音楽ファイルの生成状態を確認 {attempt}...")
            
            # test2.pyと同様のリクエスト方法
            status_url = "https://api.aimlapi.com/v2/generate/audio"
            params = {
                "generation_id": generation_id
            }
            status_headers = {
                "Authorization": f"Bearer {AIML_API_KEY}",
                "Content-Type": "application/json"
            }
            
            status_response = requests.get(status_url, params=params, headers=status_headers)
            print(f"ステータス確認レスポンス: ステータスコード={status_response.status_code}")
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"ダウンロードレスポンス: {json.dumps(status_data, ensure_ascii=False)}")
                
                # ステータスが完了しているか確認
                if status_data.get("status") == "completed":
                    # 音楽URLを取得
                    audio_url = None
                    
                    # レスポンスの形式に応じて音楽URLを取得
                    if "audio_file" in status_data and "url" in status_data.get("audio_file", {}):
                        audio_url = status_data.get("audio_file", {}).get("url")
                    elif "audio_url" in status_data:
                        audio_url = status_data.get("audio_url")
                    elif "output" in status_data and "audio" in status_data.get("output", {}):
                        audio_url = status_data.get("output", {}).get("audio")
                    
                    if audio_url:
                        print(f"音楽URL: {audio_url}")
                        
                        # 5. 結果を返す
                        print("\n=== 音楽生成プロセスが完了しました ===")
                        
                        success_data = {
                            "success": True,
                            "message": "音楽生成が完了しました",
                            "generation_id": generation_id,
                            "audio_url": audio_url,
                            "genre": genre,
                            "prompt": prompt,
                            "reference_url": reference_url,
                            "description": description,
                            "raw_response": status_data  # 生のレスポンスも含める
                        }
                        
                        return app.response_class(
                            response=json.dumps(success_data, ensure_ascii=False),
                            status=200,
                            mimetype='application/json; charset=utf-8'
                        )
                    else:
                        print("音楽URLが見つかりません。10秒後に再試行します。")
                else:
                    print(f"生成中... ステータス: {status_data.get('status')}")
            else:
                print(f"ステータス確認エラー: {status_response.status_code} - {status_response.text}")
        
        # 最大試行回数を超えた場合
        error_msg = "タイムアウト: 最大試行回数を超えました"
        print(error_msg)
        return app.response_class(
            response=json.dumps({"error": error_msg}, ensure_ascii=False),
            status=500,
            mimetype='application/json; charset=utf-8'
        )
    
    except Exception as e:
        error_msg = f"エラーが発生しました: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        error_data = {
            "error": error_msg,
            "details": "詳細はサーバーログを確認してください"
        }
        return app.response_class(
            response=json.dumps(error_data, ensure_ascii=False),
            status=500,
            mimetype='application/json; charset=utf-8'
        )

# APIエンドポイント: 生成された音楽ファイルをダウンロード
@app.route('/api/download/<filename>')
def api_download(filename):
    try:
        return send_file(os.path.join(OUTPUT_DIR, secure_filename(filename)),
                         as_attachment=True)
    except Exception as e:
        error_msg = f"ダウンロードエラー: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        error_data = {"error": error_msg}
        return app.response_class(
            response=json.dumps(error_data, ensure_ascii=False),
            status=500,
            mimetype='application/json; charset=utf-8'
        )

# APIエンドポイント: 生成状態を確認
@app.route('/api/status/<generation_id>')
def api_status(generation_id):
    try:
        # ステータス確認エンドポイント - test2.pyを参考に修正
        url = f"https://api.aimlapi.com/v2/generations/{generation_id}"
        headers = {"Authorization": f"Bearer {AIML_API_KEY}"}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            error_msg = f"ステータス確認エラー: {response.status_code} - {response.text}"
            print(error_msg)
            
            error_data = {"error": error_msg}
            return app.response_class(
                response=json.dumps(error_data, ensure_ascii=False),
                status=500,
                mimetype='application/json; charset=utf-8'
            )
    except Exception as e:
        error_msg = f"エラーが発生しました: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        error_data = {"error": error_msg}
        return app.response_class(
            response=json.dumps(error_data, ensure_ascii=False),
            status=500,
            mimetype='application/json; charset=utf-8'
        )

# ルートエンドポイント: APIドキュメント
@app.route('/')
def api_docs():
    response_data = {
        "name": "音楽生成API",
        "version": "1.0",
        "endpoints": [
            {
                "path": "/api/generate",
                "method": "GET/POST",
                "description": "音楽を生成（プロンプトはクエリパラメータまたはJSONボディから取得）",
                "parameters": [
                    {
                        "name": "prompt",
                        "type": "string",
                        "description": "音楽の説明テキスト（指定しない場合はデフォルト値を使用）"
                    }
                ]
            },
            {
                "path": "/api/download/<filename>",
                "method": "GET",
                "description": "生成された音楽ファイルをダウンロード"
            },
            {
                "path": "/api/status/<generation_id>",
                "method": "GET",
                "description": "生成状態を確認"
            }
        ],
        "default_prompt": DEFAULT_PROMPT
    }
    
    # ensure_ascii=Falseを使用して日本語をそのまま出力
    return app.response_class(
        response=json.dumps(response_data, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

# ダウンロードエンドポイント
@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(OUTPUT_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({"error": "ファイルが見つかりません"}), 404
    except Exception as e:
        error_msg = f"ダウンロードエラー: {str(e)}"
        print(error_msg)
        return jsonify({"error": error_msg}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)