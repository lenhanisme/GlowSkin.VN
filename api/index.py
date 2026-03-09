from flask import Flask, jsonify, request
import requests
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)

# Bắt đúng route /api/scraper
@app.route('/api/scraper', methods=['GET'])
def scrape_hasaki():
    # Lấy tham số 'q' từ URL, nếu không có thì mặc định tìm 'kem chống nắng'
    search_query = request.args.get('q', 'kem chống nắng')
    
    # Mã hóa từ khóa có dấu để đưa lên URL (VD: "sữa rửa mặt" -> "s%E1%BB%AFa+r%E1%BB%ADa+m%E1%BA%B7t")
    encoded_query = urllib.parse.quote_plus(search_query)
    url = f"https://hasaki.vn/catalogsearch/result/?q={encoded_query}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        products = []
        
        # Thử lấy theo cấu trúc HTML của Hasaki
        items = soup.select('.item_sp_hasaki') 
        if not items:
            items = soup.select('.ProductGridItem__itemOuter') or soup.select('.product-item')
            
        for item in items[:12]: # Giới hạn lấy 12 kết quả đầu tiên cho nhanh
            # Link
            link_tag = item.select_one('a.vn_names') or item.find('a')
            link = link_tag['href'] if link_tag and link_tag.has_attr('href') else "#"
            
            # Tên SP
            title = link_tag.text.strip() if link_tag else "Sản phẩm Hasaki"
            
            # Giá
            price_tag = item.select_one('.item_price') or item.select_one('.price')
            price = price_tag.text.strip() if price_tag else "Xem trên web"
            
            # Ảnh
            img_tag = item.select_one('img.img_sp') or item.select_one('img')
            img_url = ""
            if img_tag:
                img_url = img_tag.get('data-src') or img_tag.get('src', '')
            
            # Chỉ trả về nếu lấy được tên và ảnh
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

# Nếu Vercel route lỗi thì bắt fallback
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return scrape_hasaki()

if __name__ == '__main__':
    app.run(debug=True)
