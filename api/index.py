from flask import Flask, jsonify, request
import requests
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup
import concurrent.futures
import ssl
import time

app = Flask(__name__)

# Bỏ qua lỗi chứng chỉ SSL để tránh bị chặn gắt
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Danh sách User-Agents siêu đa dạng (Lách Cloudflare Anti-bot)
USER_AGENTS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", # Bot Google thường được cho qua
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36", # Trình duyệt thật
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15", # Mac OS
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", # Bing bot
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", # Facebook crawler
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1", # iOS
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" # Linux
]

# Các endpoint dự phòng của Hasaki (Có lúc trang search bị khóa nhưng trang ajax lại thả lỏng)
ENDPOINTS = [
    "https://hasaki.vn/catalogsearch/result?q={}",
    "https://hasaki.vn/catalogsearch/ajax/suggest?q={}",
    "https://hasaki.vn/elastic/search?q={}"
]

def parse_hasaki_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    # Gom tất cả các class mà Hasaki có thể dùng để bọc sản phẩm
    items = soup.select('.ProductGridItem__itemOuter, .item_sp_hasaki, .product-item, .item-sanpham, .v2_sp_width')
    
    for item in items[:15]: # Lấy tối đa 15 sản phẩm hiển thị ra web cho đẹp
        a_tag = item.select_one('.vn_names, .product-item-link, a.product-name, h3 a, .width_common.space_bottom_3 a') or item.find('a')
        if not a_tag:
            continue
            
        title = a_tag.text.strip()
        link = a_tag.get('href', '')
        if link and not link.startswith('http'):
            link = 'https://hasaki.vn' + link
            
        price_tag = item.select_one('.txt_price, .item_price, .price, .special-price, .item_giamoi')
        price = price_tag.text.strip() if price_tag else "Xem trên web"
        
        img_tag = item.select_one('.img_sp, .product-image-photo, img.img-responsive') or item.find('img')
        img_url = ""
        if img_tag:
            # Hasaki dùng data-src để chống load ảnh chậm (lazyload)
            img_url = img_tag.get('data-src') or img_tag.get('src', '')
            
        if title and img_url and len(title) > 3:
            products.append({
                "title": title,
                "price": price,
                "link": link,
                "image": img_url
            })
            
    return products

def execute_strategy(strategy_id, query):
    """
    Hàm thực thi 1 chiến lược cụ thể. 
    Trộn lẫn User-Agent, Endpoint và Phương pháp gọi HTTP để thử vận may.
    """
    ua = USER_AGENTS[strategy_id % len(USER_AGENTS)]
    endpoint = ENDPOINTS[strategy_id % len(ENDPOINTS)].format(urllib.parse.quote_plus(query))
    
    headers = {
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.google.com/' if strategy_id % 2 == 0 else 'https://hasaki.vn/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        # Cách 1: Dùng thư viện requests
        if strategy_id % 2 == 0:
            res = requests.get(endpoint, headers=headers, timeout=8)
            html = res.text
        # Cách 2: Dùng urllib mặc định của Python (Rất hay lách được CF)
        else:
            req = urllib.request.Request(endpoint, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=8) as response:
                html = response.read().decode('utf-8')

        # Kiểm tra xem có bị Cloudflare tóm không
        if "Just a moment..." in html or "cf-browser-verification" in html or "Enable JavaScript and cookies to continue" in html:
            raise Exception("Bị Cloudflare chặn")

        # Bắt đầu trích xuất dữ liệu
        products = parse_hasaki_html(html)
        
        # Nếu cào được > 0 sản phẩm, chiến lược này đã THẮNG!
        if len(products) > 0:
            return products
            
        raise Exception("Không tìm thấy sản phẩm hoặc bị đổi cấu trúc HTML")

    except Exception as e:
        return None  # Thất bại, trả về None để các luồng khác tiếp tục chạy

@app.route('/api/scraper', methods=['GET'])
def scrape_hasaki():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    # CHẠY ĐA LUỒNG: Tạo ra 30 chiến lược khác nhau cùng tấn công vào Hasaki
    strategies_count = 30
    
    # Mở 15 workers (luồng) chạy song song để đảm bảo tốc độ nhanh nhất
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(execute_strategy, i, query): i for i in range(strategies_count)}
        
        # Ngay khi có 1 luồng trả về kết quả thành công, lấy ngay kết quả đó và ngừng chờ!
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None and len(result) > 0:
                return jsonify(result)
                
    # Nếu cả 30 cách đều bị chặn (Rất hiếm khi xảy ra)
    return jsonify({"error": "Hệ thống Hasaki đang phòng thủ quá chặt. Thử lại từ khóa khác hoặc bấm tìm lại nhé!"})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    return scrape_hasaki()

if __name__ == '__main__':
    app.run(debug=True)
