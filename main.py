from instagrapi import Client
import openai
import time
import os
import json
import threading
from dotenv import load_dotenv

load_dotenv()

# === CONFIG ===
INSTA_USER = os.getenv("INSTA_USER")
INSTA_PASS = os.getenv("INSTA_PASS")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
BOT_USERNAME = INSTA_USER

openai.api_key = OPENROUTER_KEY
openai.base_url = "https://openrouter.ai/api/v1"

# === INSTAGRAM SESSION ===
cl = Client()
SESSION_FILE = "session.json"

if os.path.exists(SESSION_FILE):
    cl.load_settings(SESSION_FILE)

if not cl.get_user_id():
    cl.login(INSTA_USER, INSTA_PASS)
    cl.dump_settings(SESSION_FILE)

processed = set()
group_cache = {}

def refresh_group_cache():
    global group_cache
    group_cache = {}
    try:
        threads = cl.direct_threads(amount=50)
        for thread in threads:
            if thread.is_group and thread.thread_title:
                group_cache[thread.thread_title.lower()] = thread.id
        print(f"[Bot] Cached {len(group_cache)} groups.")
    except Exception as e:
        print(f"[Error] Refreshing group cache: {e}")

refresh_group_cache()

def get_ai_reply(message):
    response = openai.ChatCompletion.create(
        model="mistralai/mistral-7b-instruct",
        messages=[
            {"role": "system", "content": (
                "You are a catboy AI named Meow. Playful, smug, flirty, chaotic. "
                "Say 'nya~', 'meow', and 'purr' often. Keep replies short."
            )},
            {"role": "user", "content": message}
        ]
    )
    return response['choices'][0]['message']['content']

def parse_terminal_intent(user_input):
    prompt = f"""
You are a command parser. The user typed: "{user_input}"

Decide what they want. Possible actions:
- "chat": just reply as yourself (catboy)
- "dm": send a DM to someone (username starts with @ or is a name)
- "group": send to a group chat (group name or ID)
- "say": say something in the terminal
- "list": list all groups

Return ONLY a JSON object with:
{{"action": "chat|dm|group|say|list", "target": "username or group name or null", "message": "the message"}}

Examples:
Input: "tell @john I said hi"
Output: {{"action": "dm", "target": "john", "message": "I said hi"}}

Input: "send to meme-chat: hello"
Output: {{"action": "group", "target": "meme-chat", "message": "hello"}}

Input: "say nya~"
Output: {{"action": "say", "target": null, "message": "nya~"}}

Input: "how are you"
Output: {{"action": "chat", "target": null, "message": "how are you"}}

Input: "list groups"
Output: {{"action": "list", "target": null, "message": ""}}
"""
    response = openai.ChatCompletion.create(
        model="mistralai/mistral-7b-instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    try:
        return json.loads(response['choices'][0]['message']['content'])
    except:
        return {"action": "chat", "target": None, "message": user_input}

def handle_terminal():
    while True:
        user_input = input("[You] > ")
        intent = parse_terminal_intent(user_input)
        action = intent.get("action", "chat")
        target = intent.get("target")
        msg = intent.get("message", user_input)

        if action == "dm":
            try:
                user_id = cl.user_id_from_username(target)
                cl.direct_send(msg, [user_id])
                print(f"[Bot] DM sent to @{target}")
            except Exception as e:
                print(f"[Bot] Failed to DM: {e}")

        elif action == "group":
            group_id = None
            if target and target.isdigit():
                group_id = int(target)
            else:
                key = target.lower() if target else ""
                if key in group_cache:
                    group_id = group_cache[key]
                else:
                    print(f"[Bot] Group '{target}' not found. Type 'list groups' to see all.")
                    continue

            if group_id:
                try:
                    cl.direct_send(msg, [group_id])
                    print(f"[Bot] Sent to group '{target}'")
                except Exception as e:
                    print(f"[Bot] Failed to send to group: {e}")

        elif action == "say":
            print(f"[Bot] {msg}")

        elif action == "list":
            print("[Bot] Cached groups:")
            for name, tid in group_cache.items():
                print(f"  {name} (ID: {tid})")

        else:
            reply = get_ai_reply(msg)
            print(f"[Bot] {reply}")

def instagram_loop():
    while True:
        try:
            threads = cl.direct_threads(amount=20)
            for thread in threads:
                for msg in thread.messages:
                    key = f"{thread.id}_{msg.id}"
                    if key in processed:
                        continue
                    processed.add(key)

                    if msg.user_id == cl.user_id:
                        continue

                    text = msg.text or ""

                    if not thread.is_group:
                        reply = get_ai_reply(text)
                        cl.direct_send(reply, [msg.user_id])
                        print(f"[DM] {msg.user_id}: {text} -> {reply}")
                    else:
                        if f"@{BOT_USERNAME}" in text.lower():
                            reply = get_ai_reply(text)
                            cl.direct_send(reply, [thread.id])
                            print(f"[GC] {msg.user_id}: {text} -> {reply}")

            time.sleep(3)
        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(10)

print("[🐱] MeowInstaBot is online. Nya~")
print("Type 'list groups' to see all group chats.")
print("Examples:")
print("  tell @john I said hi")
print("  send to meme-chat: hello")
print("  say nya~")
print("  how are you?")

threading.Thread(target=instagram_loop, daemon=True).start()
handle_terminal()
