from datetime import datetime, timedelta
import re
import traceback

import requests
from bs4 import BeautifulSoup

PTT_SEARCH_URL = "https://www.ptt.cc/bbs/Stock/search"
HEADERS = {"User-Agent": "Mozilla/5.0"}
COOKIES = {"over18": "1"}
REQUEST_TIMEOUT = 12
MAX_RESULTS = 4
MAX_PUSHES = 8
_CACHE = {}


def _fetch_html(url: str):
    response = requests.get(
        url,
        headers=HEADERS,
        cookies=COOKIES,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def _normalize_query_terms(symbol: str, label: str):
    terms = [symbol.strip()]
    if label:
        clean_label = label.strip()
        if clean_label and clean_label not in terms:
            terms.append(clean_label)
    return [t for t in terms if t]


def _search_article_links(query: str, max_links: int = 8):
    html = _fetch_html(f"{PTT_SEARCH_URL}?q={requests.utils.quote(query)}")
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for entry in soup.select("div.r-ent div.title a"):
        href = entry.get("href")
        if not href:
            continue
        full_url = "https://www.ptt.cc" + href
        if full_url not in links:
            links.append(full_url)
        if len(links) >= max_links:
            break
    return links


def _extract_article_datetime(soup: BeautifulSoup):
    metas = soup.select("div.article-metaline span.article-meta-value")
    for idx, meta in enumerate(metas):
        if idx == 3:
            try:
                return datetime.strptime(meta.text.strip(), "%a %b %d %H:%M:%S %Y")
            except Exception:
                return None
    return None


def _extract_main_text(raw_text: str):
    text = raw_text.split("--", 1)[0]
    lines = []
    for line in text.splitlines():
        striped = line.strip()
        if not striped:
            continue
        if striped.startswith("作者") or striped.startswith("看板") or striped.startswith("標題") or striped.startswith("時間"):
            continue
        lines.append(striped)
    return "\n".join(lines)


def _extract_pushes(soup: BeautifulSoup, limit: int = MAX_PUSHES):
    pushes = []
    for push in soup.select("div.push"):
        tag = push.select_one("span.push-tag")
        content = push.select_one("span.push-content")
        userid = push.select_one("span.push-userid")
        if not content:
            continue
        push_text = content.text.replace(":", "", 1).strip()
        if not push_text:
            continue
        push_tag = tag.text.strip() if tag else ""
        push_user = userid.text.strip() if userid else "unknown"
        pushes.append(f"{push_tag} {push_user}: {push_text}".strip())
        if len(pushes) >= limit:
            break
    return pushes


def _fetch_article_summary(url: str):
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    article_dt = _extract_article_datetime(soup)
    title_node = soup.select_one("title")
    title = title_node.text.replace(" - 看板 Stock - 批踢踢實業坊", "").strip() if title_node else "未命名文章"
    main_node = soup.select_one("#main-content")
    raw_text = main_node.get_text("\n", strip=True) if main_node else ""
    body = _extract_main_text(raw_text)
    body = re.sub(r"\s+", " ", body).strip()
    pushes = _extract_pushes(soup)
    return {
        "date": article_dt,
        "title": title,
        "url": url,
        "body": body[:400],
        "pushes": pushes,
    }


def fetch_ptt_sentiment(symbol: str, label: str = "", days_limit: int = 30) -> str:
    cache_key = (symbol, label, days_limit)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    cutoff = datetime.now() - timedelta(days=days_limit)
    try:
        links = []
        for term in _normalize_query_terms(symbol, label):
            for url in _search_article_links(term):
                if url not in links:
                    links.append(url)

        if not links:
            result = "最近 30 天內沒有找到可用的 PTT Stock 討論。"
            _CACHE[cache_key] = result
            return result

        articles = []
        for url in links:
            article = _fetch_article_summary(url)
            if not article["date"] or article["date"] < cutoff:
                continue
            articles.append(article)
            if len(articles) >= MAX_RESULTS:
                break

        if not articles:
            result = "最近 30 天內沒有找到可驗證日期的 PTT Stock 討論。"
            _CACHE[cache_key] = result
            return result

        blocks = []
        for article in articles:
            pushes = "\n".join(f"- {push}" for push in article["pushes"]) or "- 無可用推文"
            blocks.append(
                f"【日期】{article['date']:%Y-%m-%d}\n"
                f"【來源】PTT Stock\n"
                f"【標題】{article['title']}\n"
                f"【內文摘要】{article['body'] or '無可用內文'}\n"
                f"【推文摘要】\n{pushes}\n"
                f"【連結】{article['url']}"
            )

        result = "\n\n".join(blocks)
        _CACHE[cache_key] = result
        return result
    except Exception as e:
        traceback.print_exc()
        result = f"PTT 輿情抓取失敗: {e}"
        _CACHE[cache_key] = result
        return result
