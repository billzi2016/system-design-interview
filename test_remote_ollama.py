import requests
import json

OLLAMA_HOST = "http://10.54.79.119:11434"
MODEL = "gpt-oss:120b"

def chat(prompt):
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]
    except requests.exceptions.ConnectionError:
        return f"[ERROR] 无法连接到 {OLLAMA_HOST}，请检查远程机器是否开启 Ollama"
    except requests.exceptions.Timeout:
        return "[ERROR] 请求超时"
    except Exception as e:
        return f"[ERROR] {e}"

def check_models():
    url = f"{OLLAMA_HOST}/api/tags"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return models
    except Exception as e:
        return f"[ERROR] 无法获取模型列表: {e}"

if __name__ == "__main__":
    print(f"目标: {OLLAMA_HOST}")
    print(f"模型: {MODEL}")
    print("-" * 40)

    print("可用模型列表:")
    models = check_models()
    if isinstance(models, list):
        for m in models:
            print(f"  - {m}")
    else:
        print(f"  {models}")

    print("-" * 40)
    print("发送: hello")
    reply = chat("hello")
    print(f"回复: {reply}")
