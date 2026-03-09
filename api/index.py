from flask import Flask, jsonify, request
import requests
import urllib.parse
from bs4 import BeautifulSoup
import concurrent.futures
import time

app = Flask(__name__)

# --- BỘ NHỚ ĐỆM (CACHE) ---
CACHE = {}
CACHE_TTL = 3600  # Lưu kết quả 1 tiếng cho tốc độ siêu tốc

def parse_hasaki_html(html_content):
    """Hàm bóc tách HTML chung"""
    if not html_content or "Just a moment..." in html_content or "cf-browser-verification" in html_content:
        return []
        
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    # Cấu trúc web của Hasaki
    items = soup.select('.ProductGridItem__itemOuter, .item_sp_hasaki, .product-item, .item-sanpham, .v2_sp_width')
    
    for item in items[:15]: 
        a_tag = item.select_one('.vn_names, .product-item-link, a.product-name, h3 a, .width_common.space_bottom_3 a') or item.find('a')
        if not a_tag: continue
            
        title = a_tag.text.strip()
        link = a_tag.get('href', '')
        if link and not link.startswith('http'):
            link = 'https://hasaki.vn' + link
            
        price_tag = item.select_one('.txt_price, .item_price, .price, .special-price, .item_giamoi')
        price = price_tag.text.strip() if price_tag else "Xem trên web"
        
        img_tag = item.select_one('.img_sp, .product-image-photo, img.img-responsive') or item.find('img')
        img_url = ""
        if img_tag:
            img_url = img_tag.get('data-src') or img_tag.get('src', '')
            
        if title and img_url and len(title) > 3:
            products.append({
                "title": title,
                "price": price,
                "link": link,
                "image": img_url
            })
    return products

# --- CÁC CHIẾN THUẬT VƯỢT TƯỜNG LỬA (PROXY BOUNCING) ---

def strategy_allorigins(target_url):
    """Mượn server của AllOrigins để cào giùm"""
    try:
        proxy_url = "https://api.allorigins.win/get?url=" + urllib.parse.quote(target_url)
        res = requests.get(proxy_url, timeout=15)
        html = res.json().get('contents', '')
        return parse_hasaki_html(html)
    except:
        return []

def strategy_codetabs(target_url):
    """Mượn server của CodeTabs để lách IP"""
    try:
        proxy_url = "https://api.codetabs.com/v1/proxy?quest=" + urllib.parse.quote(target_url)
        res = requests.get(proxy_url, timeout=15)
        return parse_hasaki_html(res.text)
    except:
        return []

def strategy_direct(target_url):
    """Thử đâm thẳng lỡ khi Hasaki nới lỏng bảo mật"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36'}
        res = requests.get(target_url, headers=headers, timeout=10)
        return parse_hasaki_html(res.text)
    except:
        return []


@app.route('/api/scraper', methods=['GET'])
def scrape_hasaki():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify({"data": [], "cached": False})

    # 1. Trả ngay kết quả nếu đã có người tìm trước đó (Cache)
    current_time = time.time()
    if query in CACHE:
        if current_time - CACHE[query]['timestamp'] < CACHE_TTL:
            return jsonify({"data": CACHE[query]['data'], "cached": True})
        else:
            del CACHE[query]

    encoded_query = urllib.parse.quote_plus(query)
    target_url = f"https://hasaki.vn/catalogsearch/result?q={encoded_query}"

    # 2. MỞ 3 LUỒNG SONG SONG: Ai mang dữ liệu về trước thì lấy của người đó!
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_strategy = {
            executor.submit(strategy_allorigins, target_url): "allorigins",
            executor.submit(strategy_codetabs, target_url): "codetabs",
            executor.submit(strategy_direct, target_url): "direct"
        }
        
        for future in concurrent.futures.as_completed(future_to_strategy):
            result = future.result()
            if result and len(result) > 0:
                # Lưu vào Cache và trả kết quả ngay
                CACHE[query] = {
                    'data': result,
                    'timestamp': current_time
                }
                return jsonify({"data": result, "cached": False})

    return jsonify({"error": "Hasaki phòng thủ quá chặt. Nhưng đừng lo, bạn thử bấm tìm kiếm lại lần nữa xem!"})

# Fallback cho Vercel
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return scrape_hasaki()

if __name__ == '__main__':
    app.run(debug=True)
