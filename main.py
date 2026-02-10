import os
import requests
import json
import time

# --- 設定エリア ---
# type: "page" (親ページの下に子ページを作る) or "database" (データベースに行を追加する)
# db_prop_name: データベースの場合のタイトル列の名前 (デフォルトは "Name" か "名前")
CONFIG = [
    {
        "name": "Research Ideas",
        "type": "page", 
        "discord_channel_id": "1470636620419170466",
        "target_id": "2ce11e6b4fcf8058b01fdeded6288358"
    },
    {
        "name": "YIL Ideas",
        "type": "page",
        "discord_channel_id": "1470636665566531757",
        "target_id": "2ce11e6b4fcf81638402ee60cdd974c7"
    },
    {
        "name": "Diary Log",
        "type": "database",
        "discord_channel_id": "1470636740254498987",
        "target_id": "30311e6b4fcf8053a569c8422c2e458c",
        "db_prop_name": "Name" # あなたのNotionの列名に合わせてください（英語なら "Name"）
    },
]
# ----------------

# GitHub Secretsから取得
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')

STATE_FILE = 'channel_states.json'

def get_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def create_notion_content(config, content):
    url = 'https://api.notion.com/v1/pages'
    
    # タイトル作成 (冒頭30文字)
    title_text = content[:30] + "..." if len(content) > 30 else content
    
    # 本文ブロック作成
    children = []
    for line in content.split('\n'):
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{ "type": "text", "text": { "content": line } }]
            }
        })

    payload = {
        "children": children
    }

    # 親要素とプロパティの指定 (ページとデータベースで構造が異なるため分岐)
    if config['type'] == 'database':
        # データベースの場合
        payload['parent'] = { "database_id": config['target_id'] }
        prop_name = config.get('db_prop_name', 'Name') # デフォルトはName
        payload['properties'] = {
            prop_name: { 
                "title": [{ "text": { "content": title_text } }] 
            }
        }
    else:
        # 親ページへの追加の場合
        payload['parent'] = { "page_id": config['target_id'] }
        payload['properties'] = {
            "title": [{ "text": { "content": title_text } }] # ページの場合はキーが必ず "title"
        }

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"Notion Error ({config['name']}): {resp.text}")

def add_reaction(channel_id, message_id):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/%E2%9C%85/@me"
    headers = { "Authorization": f"Bot {DISCORD_TOKEN}" }
    requests.put(url, headers=headers)

def process_channel(config, current_state):
    channel_id = config["discord_channel_id"]
    last_id = current_state.get(channel_id)
    
    print(f"--- Checking {config['name']} ---")

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"
    if last_id:
        url += f"&after={last_id}"
        
    headers = { "Authorization": f"Bot {DISCORD_TOKEN}" }
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        print(f"Discord Error {channel_id}: {resp.text}")
        return last_id

    messages = resp.json()
    if not messages: return last_id

    messages.reverse()
    new_last_id = last_id
    
    for msg in messages:
        if msg['author'].get('bot', False): continue
            
        print(f"Syncing: {msg['content'][:20]}...")
        create_notion_content(config, msg['content'])
        add_reaction(channel_id, msg['id'])
        new_last_id = msg['id']
        time.sleep(1)

    return new_last_id

def main():
    state = get_state()
    for config in CONFIG:
        try:
            if not config["target_id"]: continue # ID未設定ならスキップ
            updated_id = process_channel(config, state)
            if updated_id:
                state[config["discord_channel_id"]] = updated_id
        except Exception as e:
            print(f"Error processing {config['name']}: {e}")
    save_state(state)

if __name__ == "__main__":
    main()
