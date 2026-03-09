from flask import Flask, jsonify, request
import requests
import urllib.parse

app = Flask(__name__)

# --- CACHE ---
CACHE = {}

def get_tiki_data(keyword):
    """
    Sử dụng API nội bộ của Tiki. Vercel gọi thoải mái không bị chặn IP!
    """
    encoded_keyword = urllib.parse.quote(keyword)
    # API Tiki: Giới hạn 20 sản phẩm, tìm theo từ khóa
    url = f"https://tiki.vn/api/v2/products?limit=20&q={encoded_keyword}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status() # Báo lỗi ngay nếu Tiki sập
        data = res.json()

        items = data.get('data', [])
        results = []

        for item in items:
            name = item.get('name')
            price_raw = item.get('price', 0)
            image_url = item.get('thumbnail_url')
            url_path = item.get('url_path')

            if not name or not image_url or not url_path:
                continue

            # Format giá tiền (VD: 299000 -> 299.000 đ)
            price = "{:,.0f} đ".format(price_raw).replace(',', '.')
            
            # Tiki API trả về url_path, mình ghép thêm domain vào
            link = f"https://tiki.vn/{url_path}"

            results.append({
                "title": name,
                "price": price,
                "image": image_url,
                "link": link
            })

        return results
    except Exception as e:
        print(f"Lỗi Tiki API: {e}")
        return []

@app.route('/api/scraper', methods=['GET'])
def scrape_api():
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({"error": "Vui lòng cung cấp từ khóa tìm kiếm!"})

    # Dùng Cache để tăng tốc
    if query in CACHE:
        return jsonify({"data": CACHE[query], "cached": True})

    data = get_tiki_data(query)
    
    if len(data) > 0:
        CACHE[query] = data
        return jsonify({"data": data, "cached": False})
    else:
        return jsonify({"error": "Không tìm thấy sản phẩm trên Tiki. Bạn thử từ khóa khác nhé!"})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return scrape_api()

if __name__ == '__main__':
    app.run(debug=True)
