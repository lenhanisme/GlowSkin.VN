from flask import Flask, jsonify, request
import requests
import urllib.parse
import concurrent.futures
import time
import json

app = Flask(__name__)

# --- BỘ NHỚ ĐỆM (CACHE) ---
CACHE = {}
CACHE_TTL = 3600  # Lưu cache 1 tiếng

def parse_shopee_json(data):
    """Hàm bóc tách dữ liệu JSON từ API nội bộ của Shopee"""
    products = []
    try:
        # Tùy phiên bản API, danh sách sp nằm ở 'items'
        items = data.get('items', [])
        
        for item_wrapper in items[:15]: 
            # Shopee bọc dữ liệu trong item_basic
            item = item_wrapper.get('item_basic', item_wrapper)
            
            name = item.get('name')
            price_raw = item.get('price', 0)
            
            if not name or not price_raw:
                continue
                
            # Giá trên API Shopee luôn bị nhân lên 100,000 lần (VD: 15000000000 = 150,000đ)
            real_price = price_raw / 100000
            price_formatted = "{:,.0f} đ".format(real_price).replace(',', '.')
            
            # Xử lý hình ảnh (Shopee dùng server ảnh tĩnh susercontent)
            image_id = item.get('image')
            image_url = f"https://down-vn.img.susercontent.com/file/{image_id}" if image_id else ""
            
            # Tạo link mua hàng trực tiếp (dùng shopid và itemid)
            shopid = item.get('shopid')
            itemid = item.get('itemid')
            link = f"https://shopee.vn/product/{shopid}/{itemid}"
            
            products.append({
                "title": name,
                "price": price_formatted,
                "link": link,
                "image": image_url
            })
    except Exception as e:
        print("Lỗi phân tích JSON Shopee:", e)
        
    return products


def strategy_direct(query):
    """Đóng giả trình duyệt gọi thẳng API Shopee"""
    try:
        encoded_query = urllib.parse.quote(query)
        # API chuẩn của Shopee Mall (Lọc theo danh mục Mall, giới hạn 15 sp)
        url = f"https://shopee.vn/api/v4/search/search_items?by=relevancy&keyword={encoded_query}&limit=15&newest=0&order=desc&page_type=search&scenario=PAGE_MALL_SEARCH&version=2"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': f'https://shopee.vn/mall/search?keyword={encoded_query}',
            'x-api-source': 'pc',
            'accept-language': 'vi-VN,vi;q=0.9,en-US;q=0.8'
        }
        
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        return parse_shopee_json(data)
    except:
        return []

def strategy_proxy_origins(query):
    """Nhờ server AllOrigins gọi hộ API nếu Vercel bị chặn"""
    try:
        encoded_query = urllib.parse.quote(query)
        target_url = f"https://shopee.vn/api/v4/search/search_items?by=relevancy&keyword={encoded_query}&limit=15&newest=0&page_type=search&scenario=PAGE_MALL_SEARCH"
        proxy_url = "https://api.allorigins.win/get?url=" + urllib.parse.quote(target_url)
        
        res = requests.get(proxy_url, timeout=15)
        contents = res.json().get('contents', '{}')
        data = json.loads(contents)
        return parse_shopee_json(data)
    except:
        return []

@app.route('/api/scraper', methods=['GET'])
def scrape_shopee():
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify({"data": [], "cached": False})

    # Kiểm tra Cache
    current_time = time.time()
    if query in CACHE:
        if current_time - CACHE[query]['timestamp'] < CACHE_TTL:
            return jsonify({"data": CACHE[query]['data'], "cached": True})
        else:
            del CACHE[query]

    # Đua đa luồng: Ai lấy được JSON trước thì ăn!
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(strategy_direct, query): "direct",
            executor.submit(strategy_proxy_origins, query): "proxy"
        }
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result and len(result) > 0:
                CACHE[query] = {
                    'data': result,
                    'timestamp': current_time
                }
                return jsonify({"data": result, "cached": False})

    return jsonify({"error": "Shopee đang từ chối truy cập hoặc từ khóa này không có sản phẩm Mall nào!"})

# Fallback cho Vercel
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return scrape_shopee()

if __name__ == '__main__':
    app.run(debug=True)
