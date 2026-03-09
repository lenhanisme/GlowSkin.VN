from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)

@app.route('/api/scraper', methods=['GET'])
def scrape_hasaki():
    # Nhận từ khóa từ Frontend (người dùng nhập gì sẽ vào đây)
    search_query = request.args.get('q', 'serum')
    
    # Mã hóa URL (VD: "sữa rửa mặt" -> "s%E1%BB%AFa+r%E1%BB%ADa...")
    encoded_query = urllib.parse.quote_plus(search_query)
    
    # URL chuẩn của Hasaki (ĐÃ FIX: Bỏ dấu / trước ?q=)
    url = f"https://hasaki.vn/catalogsearch/result?q={encoded_query}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        products = []
        
        # Hasaki sử dụng nhiều class khác nhau tùy vào loại sản phẩm hiển thị.
        # Chúng ta sẽ quét qua các class phổ biến nhất của họ.
        items = soup.select('.ProductGridItem__itemOuter')
        if not items:
            items = soup.select('.item_sp_hasaki')
        if not items:
            items = soup.select('.product-item')
            
        for item in items[:15]: # Lấy 15 sản phẩm liên quan nhất
            # Lấy Link và Tên SP
            a_tag = item.select_one('.vn_names') or item.select_one('.product-item-link') or item.find('a')
            if not a_tag:
                continue
                
            title = a_tag.text.strip()
            link = a_tag.get('href', '')
            
            # Lấy Giá (Tìm thẻ chứa chữ 'đ' hoặc class price)
            price_tag = item.select_one('.txt_price') or item.select_one('.item_price') or item.select_one('.price')
            price = price_tag.text.strip() if price_tag else "Xem trên web"
            
            # Lấy Ảnh (Hasaki thường dùng data-src cho Lazyload)
            img_tag = item.select_one('.img_sp') or item.select_one('.product-image-photo') or item.find('img')
            img_url = ""
            if img_tag:
                img_url = img_tag.get('data-src') or img_tag.get('src', '')
            
            if title and img_url:
                products.append({
                    "title": title,
                    "price": price,
                    "link": link,
                    "image": img_url
                })

        return jsonify(products)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return scrape_hasaki()

if __name__ == '__main__':
    app.run(debug=True)
