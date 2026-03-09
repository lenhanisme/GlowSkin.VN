from flask import Flask, jsonify, request
import requests
import urllib.parse

app = Flask(__name__)

CACHE = {}

def get_tiki_data(keyword):
    encoded_keyword = urllib.parse.quote(keyword)
    url = f"https://tiki.vn/api/v2/products?limit=20&q={encoded_keyword}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status() 
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

        price = "{:,.0f} đ".format(price_raw).replace(',', '.')
        link = f"https://tiki.vn/{url_path}"

        results.append({
            "title": name,
            "price": price,
            "image": image_url,
            "link": link
        })

    return results

@app.route('/api/scraper', methods=['GET'])
def scrape_api():
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({"error": "Vui lòng cung cấp từ khóa tìm kiếm!"})

        if query in CACHE:
            return jsonify({"data": CACHE[query], "cached": True})

        data = get_tiki_data(query)
        
        if len(data) > 0:
            CACHE[query] = data
            return jsonify({"data": data, "cached": False})
        else:
            return jsonify({"error": "Không tìm thấy sản phẩm trên Tiki. Bạn thử từ khóa khác nhé!"})
            
    except Exception as e:
        # Bắt toàn bộ lỗi sập server và trả về UI để dễ debug
        return jsonify({"error": f"Lỗi Python Backend: {str(e)}"})

# Bắt tất cả các đường link khác để tránh lỗi 404
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return jsonify({"error": "Đã kết nối API nhưng sai đường dẫn. Hãy gọi vào /api/scraper"})

# Cấu hình CORS để Frontend gọi API không bị trình duyệt chặn
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    app.run(debug=True)
