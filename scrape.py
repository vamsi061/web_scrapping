# filename: infofetcher_api.py

from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from collections import Counter
from urllib.parse import urljoin
from googlesearch import search
from flask import Flask, request, jsonify
from flask_cors import CORS  # <--- Add this

app = Flask(__name__)
CORS(app)  # <--- Add this too


role_to_person = {
    "cm of ap": "Y. S. Jagan Mohan Reddy",
    "pm of india": "Narendra Modi",
    "president of india": "Droupadi Murmu",
    "cm of tamil nadu": "M. K. Stalin",
    "cm of maharashtra": "Eknath Shinde",
    "cm of uttar pradesh": "Yogi Adityanath",
}

def perform_google_search(query, num_results=7):
    try:
        return list(search(query, num_results=num_results))
    except Exception:
        return []

def scrape_website(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except requests.RequestException:
        return None

def extract_headings_paragraphs_and_profile_images(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    content = []
    images = []

    for tag in soup.find_all(['h1', 'h2', 'h3', 'p']):
        text = tag.get_text().strip()
        if text:
            content.append(text)

    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or ""
        alt = img.get('alt', "").lower()
        class_list = " ".join(img.get('class', [])).lower()
        if src and not src.startswith("data:"):
            full_url = urljoin(base_url, src)
            if any(k in class_list for k in ['avatar', 'profile', 'user', 'photo', 'profile-pic']) or 'avatar' in alt or 'profile' in alt:
                images.append(full_url)
            elif full_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                images.append(full_url)

    for tag in soup.find_all(['div', 'span', 'section']):
        style = tag.get('style', '')
        if 'background-image' in style:
            start_idx = style.find('url(')
            end_idx = style.find(')', start_idx)
            if start_idx != -1 and end_idx != -1:
                bg_url = style[start_idx+4:end_idx].strip('\'"')
                if bg_url:
                    full_url = urljoin(base_url, bg_url)
                    images.append(full_url)

    return content, list(set(images))

def relevance_score(text, query):
    return SequenceMatcher(None, text.lower(), query.lower()).ratio()

def clean_text(texts):
    seen = set()
    cleaned = []
    for text in texts:
        if text not in seen and len(text.split()) > 5:
            seen.add(text)
            cleaned.append(text)
    return cleaned

def summarize_text(texts, max_sentences=8):
    flat_text = ' '.join(texts)
    sentences = flat_text.split('. ')
    ranked = Counter(sentences)
    top = [s for s, _ in ranked.most_common(max_sentences)]
    return '. '.join(top)

@app.route("/")
def home():
    return jsonify({
        "message": "Welcome to Deep InfoFetcher API. Use /search endpoint with ?query=your-question"
    })

@app.route("/api/search", methods=["GET"])
def search_api():
    query = request.args.get("query", "").strip()

    if not query:
        return jsonify({"status": "error", "message": "Please provide a query parameter"}), 400

    normalized_query = query.lower()
    identified_person = None

    for role, person in role_to_person.items():
        if role in normalized_query:
            query = person
            identified_person = person
            break

    urls = perform_google_search(query, num_results=7)
    if not urls:
        return jsonify({"status": "error", "message": "No search results found"}), 404

    all_texts, all_images = [], []
    for url in urls:
        html = scrape_website(url)
        if html:
            texts, imgs = extract_headings_paragraphs_and_profile_images(html, url)
            if texts:
                top_texts = sorted(texts, key=lambda t: relevance_score(t, query), reverse=True)[:5]
                all_texts.extend(top_texts)
            all_images.extend(imgs)

    if not all_texts:
        return jsonify({"status": "error", "message": "Failed to extract relevant information"}), 500

    cleaned_texts = clean_text(all_texts)
    summary = summarize_text(cleaned_texts)

    return jsonify({
        "status": "success",
        "query": query,
        "role_matched": identified_person or "N/A",
        "summary": summary.strip(),
        "sources": urls,
        "profile_images": list(set(all_images))[:5]
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
