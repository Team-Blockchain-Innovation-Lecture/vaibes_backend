import requests
import json
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction, GetLatestBlockhash
from solders.rpc.config import RpcSendTransactionConfig
import time
import traceback
import os
from dotenv import load_dotenv
from solders.hash import Hash
from solders.message import Message

# 環境変数を読み込む
load_dotenv()

def send_local_create_tx():
    signer_keypair_str = os.getenv('SIGNER_KEYPAIR')
    if not signer_keypair_str:
        raise ValueError("SIGNER_KEYPAIR environment variable is not set")
    
    signer_keypair = Keypair.from_base58_string(signer_keypair_str)

    # Generate a random keypair for token
    mint_keypair = Keypair()

    # Define token metadata
    form_data = {
        'name': 'Vaibes.fun',
        'symbol': 'VAIBES',
        'description': 'This is Vaibes.fun',
        'website': 'https://vaibes.fun',
        'showName': 'true'
    }

    # Read the image file
    with open('./example.png', 'rb') as f:
        file_content = f.read()

    files = {
        'file': ('example.png', file_content, 'image/png')
    }

    # Create IPFS metadata storage
    metadata_response = requests.post("https://pump.fun/api/ipfs", data=form_data, files=files)
    metadata_response_json = metadata_response.json()

    # Token metadata
    token_metadata = {
        'name': form_data['name'],
        'symbol': form_data['symbol'].upper(),
        'uri': metadata_response_json['metadataUri'],
        'decimals': 9,
        'sellerFeeBasisPoints': 0,
        'creators': None,  # クリエイター情報を明示的にNullに
        'collection': None  # コレクション情報も明示的にNullに
    }

    # Generate the create transaction
    response = requests.post(
        "https://pumpportal.fun/api/trade-local",
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'publicKey': str(signer_keypair.pubkey()),
            'action': 'create',
            'tokenMetadata': token_metadata,
            'mint': str(mint_keypair.pubkey()),
            'denominatedInSol': 'true',
            'amount': 0.05,  # 金額を増やす
            'slippage': 0.5,  # スリッページを調整
            'priorityFee': 0.005,  # 優先手数料を増やす
            'pool': 'pump'
        })
    )

    # 最新のブロックハッシュを取得
    print("Getting latest blockhash...")
    blockhash_response = requests.post(
        url="https://api.mainnet-beta.solana.com",
        headers={"Content-Type": "application/json"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getLatestBlockhash",
            "params": []
        }
    )
    
    blockhash_data = blockhash_response.json()
    if 'error' in blockhash_data:
        print("Error getting blockhash:", blockhash_data['error'])
        return
    
    blockhash = blockhash_data['result']['value']['blockhash']
    print(f"Latest blockhash: {blockhash}")

    # トランザクションを生成（署名の順序を確認）
    print("Mint pubkey:", mint_keypair.pubkey())
    print("Signer pubkey:", signer_keypair.pubkey())
    tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [signer_keypair, mint_keypair])
    
    # ブロックハッシュを明示的に設定
    transaction_message = VersionedTransaction.from_bytes(response.content).message
    transaction_message.recent_blockhash = Hash.from_string(blockhash)
    
    # トランザクション設定
    commitment = CommitmentLevel.Confirmed
    config = RpcSendTransactionConfig(
        preflight_commitment=commitment,
        skip_preflight=True  # プリフライトチェックをスキップ
    )
    txPayload = SendVersionedTransaction(tx, config)

    # トランザクションを送信
    print("Sending transaction...")
    response = requests.post(
        url="https://api.mainnet-beta.solana.com",
        headers={"Content-Type": "application/json"},
        data=txPayload.to_json()
    )

    print("Response status:", response.status_code)
    response_data = response.json()
    
    if 'error' in response_data:
        print("Transaction Error:", response_data['error'])
        if 'data' in response_data['error']:
            print("Error Data:", response_data['error']['data'])
        return
    
    txSignature = response_data.get('result')
    if txSignature:
        print(f'Transaction: https://solscan.io/tx/{txSignature}')
        print("Waiting for confirmation...")
        time.sleep(5)  # トランザクションの確認を待つ
    else:
        print("No transaction signature in response")

    # レスポンスの内容を確認するコードを追加
    print("PumpPortal API Response:", response.status_code)
    print("PumpPortal API Content:", response.text)

    try:
        # PumpPortalのレスポンスを詳細に確認
        response = requests.post(
            "https://pumpportal.fun/api/trade-local",
            headers={'Content-Type': 'application/json'},
            data=json.dumps({
                'publicKey': str(signer_keypair.pubkey()),
                'action': 'create',
                'tokenMetadata': token_metadata,
                'mint': str(mint_keypair.pubkey()),
                'denominatedInSol': 'true',
                'amount': 0.05,
                'slippage': 1,
                'priorityFee': 0.002,
                'pool': 'pump'
            })
        )
        print("Initial API Response:", response.status_code)
        print("Initial API Content:", response.text)

        # トランザクションの内容を確認
        transaction_message = VersionedTransaction.from_bytes(response.content).message
        print("Required signers:", transaction_message.account_keys)
        print("Message header:", transaction_message.header)
        print("Instructions:", transaction_message.instructions)
    except Exception as e:
        print(f"Error processing response: {str(e)}")
        traceback.print_exc()

send_local_create_tx()