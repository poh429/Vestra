import os
import json
import requests
from dotenv import load_dotenv

def get_openrouter_api_key():
    load_dotenv(os.path.join(os.getcwd(), '.env'))
    return os.getenv("OPENROUTER_API_KEY")

def stream_ai_summary(symbol: str, news_text: str):
    """
    Generator that yields chunks of the AI's summary text.
    Uses OpenRouter API to fetch a summary of the news.
    """
    api_key = get_openrouter_api_key()
    if not api_key:
        yield "系統找不到 OPENROUTER_API_KEY，請確認 .env 檔案設定。\n您可以點擊下方按鈕，直接前往網頁版 Gemini 詢問！"
        return
        
    prompt = f"""請幫我分析以下關於 {symbol} 的近期新聞與資訊，並嚴格遵循以下格式使用繁體中文輸出：

1. 🔥 近期多方動能 (利多):
(列出 1~3 點最重要的好消息)

2. 🧊 潛在空方風險 (利空):
(列出 1~3 點需要注意的壞消息或隱憂)

3. 📝 總結判定:
(以一句話總結當前短線情緒，例如：整體情緒偏多/中立/偏空/狂熱/恐慌)

新聞資訊如下：
{news_text}
"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/poh429/Vestra",
        "X-Title": "Vestra Stock Widget"
    }
    
    # We use a free fast model or fallback
    data = {
        "model": "openrouter/free",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": 500,
        "temperature": 0.3
    }

    try:
        # Fallback list of models in case one is restricted or offline
        models_to_try = [
            "openrouter/free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-3-27b-it:free",
            "qwen/qwen3-coder:free",
            "mistralai/mistral-small-3.1-24b-instruct:free"
        ]
        
        response = None
        for model in models_to_try:
            data["model"] = model
            try:
                # Use stream=True to get chunks
                response = requests.post(url, headers=headers, json=data, stream=True, timeout=10)
                if response.status_code == 200:
                    break
            except Exception:
                pass
                
        if not response or response.status_code != 200:
            yield "OpenRouter API 呼叫失敗，或無可用之免費模型。\n您可以點擊下方按鈕，複製提示詞並手動前往 Gemini 查詢。"
            return

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    content = line[6:]
                    if content == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(content)
                        delta = chunk_json['choices'][0]['delta']
                        if 'content' in delta:
                            yield delta['content']
                    except Exception:
                        pass
    except Exception as e:
        yield f"\n[連線錯誤] {str(e)}\n\n請以瀏覽器備案為主。"
