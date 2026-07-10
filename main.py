from instagrapi import Client
import openai
import time
import os
import json
from dotenv import load_dotenv

load_dotenv()

INSTA_USER = os.getenv("INSTA_USER")
INSTA_PASS = os.getenv("INSTA_PASS")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")
BOT_USERNAME = INSTA_USER

openai.api_key = OPENROUTER_KEY
openai.base_url = "https://openrouter.ai/api/v1"

cl = Client()
SESSION_FILE = "session.json"

if os.path.exists(SESSION_FILE):
    cl.load_settings(SESSION_FILE)

if not cl.get_user_id():
    cl.login(INSTA_USER, INSTA_PASS)
    cl.dump_settings(SESSION_FILE)

processed = set()

def get_ai_reply(message):
    response = openai.ChatCompletion.create(
        model="mistralai/mistral-7b-instruct",
        messages=[
            {"role": "system", "content": (
                "You are a catboy AI named Meow. Playful, smug, flirty. "
                "Say nya~, meow, purr. Keep replies short."
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
- "dm": send a DM to someone
- "say": say something in the terminal (or group)

Return ONLY a JSON object with:
{{"action": "chat|dm|say", "target": "username or null", "message": "the message"}}

Example:
Input: "tell @john I said hi"
Output: {{"action": "dm", "target": "john", "message": "I said hi"}}

Input: "say nya~"
Output: {{"action": "say", "target": null, "message": "nya~"}}

Input: "how are you"
Output: {{"action": "chat", "target": null, "message": "how are you"}}
"""
    response = openai.ChatCompletion.create(
        model="mistralai/mistral-7b-instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100
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
                print(f"[Bot] Sent DM to @{target}")
            except:
                print("[Bot] User not found or error sending DM.")
        elif action == "say":
            print(f"[Bot] {msg}")
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
                    else:
                        if f"@{BOT_USERNAME}" in text.lower():
                            reply = get_ai_reply(text)
                            cl.direct_send(reply, [thread.id])
            time.sleep(3)
        except Exception as e:
            print(f"[Error] {e}")
            time.sleep(10)

print("[🐱] MeowInstaBot is online. Nya~")
print("Just talk to it naturally. It'll figure out what you want.")

import threading
threading.Thread(target=instagram_loop, daemon=True).start()
handle_terminal()