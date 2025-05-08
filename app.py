from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Cho phép Cross-Origin Resource Sharing (CORS)

REST_COUNTRIES_API_URL = "https://restcountries.com/v3.1/name/"

@app.route('/')
def index():
    # Route đơn giản để kiểm tra server có chạy không
    return "Chào mừng đến với Agent Tra Cứu Quốc Gia!"

@app.route('/get_country_info', methods=['GET'])
def get_country_info():
    # Lấy tên quốc gia từ query parameter 'country_name'
    country_name = request.args.get('country_name')

    if not country_name:
        return jsonify({"error": "Vui lòng cung cấp tên quốc gia."}), 400

    try:
        # Gọi API Rest Countries
        response = requests.get(f"{REST_COUNTRIES_API_URL}{country_name}?fullText=true") # fullText=true để tìm kiếm chính xác tên

        # Kiểm tra mã trạng thái phản hồi từ API
        if response.status_code == 404:
            # Nếu không tìm thấy quốc gia
            return jsonify({"error": f"Không tìm thấy thông tin cho quốc gia '{country_name}'."}), 404
        elif response.status_code != 200:
            # Các lỗi khác từ API (ví dụ: server error)
            return jsonify({"error": f"Có lỗi xảy ra khi tra cứu thông tin quốc gia. Mã lỗi: {response.status_code}"}), response.status_code

        # Parse dữ liệu JSON từ API
        data = response.json()

        # API Rest Countries trả về một danh sách các kết quả (có thể có nhiều quốc gia cùng tên hoặc gần giống),
        # chúng ta lấy kết quả đầu tiên
        if not data:
            return jsonify({"error": f"Không tìm thấy thông tin chi tiết cho quốc gia '{country_name}'."}), 404

        country_data = data[0] # Lấy kết quả đầu tiên

        # Trích xuất thông tin cần thiết
        name = country_data.get('name', {}).get('common', 'Không có thông tin')
        capital = country_data.get('capital', ['Không có thông tin'])[0] if country_data.get('capital') else 'Không có thông tin'
        population = country_data.get('population', 'Không có thông tin')
        region = country_data.get('region', 'Không có thông tin')
        subregion = country_data.get('subregion', 'Không có thông tin')

        # Trích xuất đơn vị tiền tệ
        currencies = country_data.get('currencies')
        currency_info = 'Không có thông tin'
        if currencies:
            currency_list = [f"{curr.get('name', 'Không tên')} ({curr.get('symbol', 'Không ký hiệu')})" for curr_code, curr in currencies.items()]
            currency_info = ", ".join(currency_list)

        # Trích xuất ngôn ngữ
        languages = country_data.get('languages')
        language_info = 'Không có thông tin'
        if languages:
            language_list = [lang for lang_code, lang in languages.items()]
            language_info = ", ".join(language_list)

        # Trả về thông tin dưới dạng JSON
        return jsonify({
            "name": name,
            "capital": capital,
            "population": population,
            "region": region,
            "subregion": subregion,
            "currency": currency_info,
            "language": language_info
        })

    except requests.exceptions.RequestException as e:
        # Xử lý lỗi khi gọi API (ví dụ: mất mạng)
        return jsonify({"error": f"Lỗi kết nối đến API tra cứu: {e}"}), 500
    except Exception as e:
        # Xử lý các lỗi không mong muốn khác
        return jsonify({"error": f"Đã xảy ra lỗi nội bộ: {e}"}), 500

if __name__ == '__main__':
    # Chạy ứng dụng Flask ở chế độ debug
    app.run(debug=True, port=5000) # Chạy trên cổng 5000