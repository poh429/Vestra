import os
import json
from datetime import datetime, timedelta
import requests
from requests.exceptions import ReadTimeout, RequestException
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FREE_MODELS_FILE = os.path.join(BASE_DIR, "free_models.txt")

DEFAULT_MODELS = [
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-coder:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]

def get_openrouter_api_key():
    # Prefer project root .env (c:\stock_project\.env), fall back to CWD.
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)
    load_dotenv(os.path.join(os.getcwd(), ".env"), override=False)
    return os.getenv("OPENROUTER_API_KEY")

def _load_free_models():
    models = []
    if os.path.exists(FREE_MODELS_FILE):
        try:
            with open(FREE_MODELS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    m = line.strip()
                    if not m or m.startswith("#"):
                        continue
                    if m != "openrouter/free" and ":free" not in m:
                        continue
                    models.append(m)
        except Exception:
            models = []
    if not models:
        models = list(DEFAULT_MODELS)
    # De-dup while preserving order
    seen = set()
    ordered = []
    for m in models:
        if m in seen:
            continue
        seen.add(m)
        ordered.append(m)
    return ordered


def _stream_openrouter_prompt(prompt: str):
    api_key = get_openrouter_api_key()
    if not api_key:
        yield "系統找不到 OPENROUTER_API_KEY，請確認 .env 檔案設定。"
        return

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/poh429/Vestra",
        "X-Title": "Vestra Stock Widget"
    }
    data = {
        "model": "openrouter/free",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": 500,
        "temperature": 0.3
    }

    try:
        models_to_try = _load_free_models()
        response = None

        for model in models_to_try:
            data["model"] = model
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    stream=True,
                    timeout=(4, 8),
                )
            except RequestException:
                continue

            if response.status_code != 200:
                try:
                    response.close()
                except Exception:
                    pass
                continue

            got_any = False
            try:
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data: "):
                        content = line[6:]
                        if content == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(content)
                            delta = chunk_json["choices"][0]["delta"]
                            if "content" in delta:
                                got_any = True
                                yield delta["content"]
                        except Exception:
                            pass
                if got_any:
                    try:
                        response.close()
                    except Exception:
                        pass
                    return
            except ReadTimeout:
                if got_any:
                    yield "\n\n[連線逾時] 回應中斷，請改用瀏覽器備案。\n"
                    try:
                        response.close()
                    except Exception:
                        pass
                    return
                continue
            finally:
                try:
                    response.close()
                except Exception:
                    pass

        yield "OpenRouter API 呼叫失敗，或無可用之免費模型。\n您可以點擊下方按鈕，複製提示詞並手動前往 Gemini 或 Perplexity 查詢。"
        return
    except Exception as e:
        yield f"\n[連線錯誤] {str(e)}\n\n請以瀏覽器備案為主。"

def stream_ai_summary(symbol: str, news_text: str):
    """
    Generator that yields chunks of the AI's summary text.
    Uses OpenRouter API to fetch a summary of the news.
    """
    if not get_openrouter_api_key():
        yield "系統找不到 OPENROUTER_API_KEY，請確認 .env 檔案設定。\n您可以點擊下方按鈕，直接前往網頁版 Gemini 詢問！"
        return
        
    today = datetime.now().date()
    start_date = today - timedelta(days=7)
    prompt = f"""請幫我分析以下關於 {symbol} 的近期新聞與資訊，並嚴格遵循以下格式使用繁體中文輸出：

今天日期是 {today:%Y-%m-%d}。
你只能採用 {start_date:%Y-%m-%d} 到 {today:%Y-%m-%d} 之間的資訊。
如果資料早於 {start_date:%Y-%m-%d}、日期不明，或無法確認時間，一律忽略，不得引用。
若最近 7 天資料不足，請直接明說「最近 7 天可用資訊不足」。

1. 🔥 近期多方動能 (利多):
(列出 1~3 點最重要的好消息)

2. 🧊 潛在空方風險 (利空):
(列出 1~3 點需要注意的壞消息或隱憂)

3. 📝 總結判定:
(以一句話總結當前短線情緒，例如：整體情緒偏多/中立/偏空/狂熱/恐慌)

新聞資訊如下：
{news_text}
"""
    yield from _stream_openrouter_prompt(prompt)


def stream_ptt_sentiment_summary(symbol: str, discussion_text: str):
    if not get_openrouter_api_key():
        yield "系統找不到 OPENROUTER_API_KEY，請確認 .env 檔案設定。"
        return

    today = datetime.now().date()
    start_date = today - timedelta(days=30)
    prompt = f"""請根據以下 PTT Stock 版關於 {symbol} 的近 30 天討論，使用繁體中文輸出摘要。

今天日期是 {today:%Y-%m-%d}。
你只能採用 {start_date:%Y-%m-%d} 到 {today:%Y-%m-%d} 之間的討論。
如果資料不足，請直接明說「最近 30 天 PTT 可用討論不足」。
請特別區分文章主文觀點與推文情緒，不要把單一留言誇大成市場共識。

輸出格式：
1. 整體輿情傾向:
(偏多 / 中立 / 偏空，並用一句話說明)

2. 多方主要論點:
(列出 1~3 點)

3. 空方主要論點:
(列出 1~3 點)

4. 爭議焦點與雜訊:
(列出 1~2 點，指出哪些是情緒發洩、反串或樣本不足)

PTT 討論資料如下：
{discussion_text}
"""
    yield from _stream_openrouter_prompt(prompt)
