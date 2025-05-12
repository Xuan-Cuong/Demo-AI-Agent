from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import sys
import re # Import regex module

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# --- Configuration ---
REST_COUNTRIES_API_URL = "https://restcountries.com/v3.1/name/"
REST_COUNTRIES_ALL_URL = "https://restcountries.com/v3.1/all" # For potentially loading all countries/languages
OPENWEATHERMAP_API_URL = "https://api.openweathermap.org/data/2.5/weather?"
EXCHANGERATE_API_URL = "https://v6.exchangerate-api.com/v6/" # Example: Free API from exchangerate-api.com
NEWSAPI_API_URL = "https://newsapi.org/v2/everything?"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY") # Need to sign up for a free key
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY") # Need to sign up for a free key


# --- Initialize Google AI ---
if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY not found in .env file. AI capabilities will be limited.")
    model = None
else:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        # Use a suitable model. gemini-2.5-flash-preview-04-17 is fast and cheap.
        # gemini-1.5-pro might be better for complex tasks but costs more.
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
        # Alternative: Use a chat-optimized model if available and suitable
        # model = genai.GenerativeModel('gemini-1.5-flash-latest') # Example
        print("Google AI model initialized successfully.")
    except Exception as e:
        print(f"Error initializing Google AI: {e}")
        model = None

# --- Helper functions for external APIs ---

def get_country_data(country_name):
    """Fetches country data from Restcountries API."""
    if not country_name:
        return None
    try:
        encoded_name = requests.utils.quote(country_name)
        response = requests.get(f"{REST_COUNTRIES_API_URL}{encoded_name}")
        response.raise_for_status()
        data = response.json()
        if not data or ('status' in data and data['status'] == 404):
             return None
        # Find exact match or first result
        # A more robust way would match based on name, official name, etc.
        # For simplicity, return the first result.
        return data[0]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching country data for {country_name}: {e}")
        return None

def get_weather_data(lat, lon):
    """Fetches weather data from OpenWeatherMap API."""
    if not OPENWEATHERMAP_API_KEY:
        print("OpenWeatherMap API key not configured.")
        return None
    try:
        response = requests.get(f"{OPENWEATHERMAP_API_URL}lat={lat}&lon={lon}&appid={OPENWEATHERMAP_API_KEY}&units=metric&lang=vi")
        response.raise_for_status()
        data = response.json()
        # Extract relevant info
        weather_info = {
            "description": data['weather'][0]['description'].capitalize() if data.get('weather') else 'N/A',
            "temp": data['main']['temp'] if data.get('main') else 'N/A',
            "feels_like": data['main']['feels_like'] if data.get('main') else 'N/A',
            "humidity": data['main']['humidity'] if data.get('main') else 'N/A',
            "wind_speed": data['wind']['speed'] if data.get('wind') else 'N/A',
            "city_name": data.get('name', 'Vị trí này')
        }
        return weather_info
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data for {lat},{lon}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing weather data: {e}")
        return None

def get_exchange_rate(base_currency_code):
    """Fetches exchange rate against USD from ExchangeRate-API."""
    if not EXCHANGERATE_API_KEY:
         print("ExchangeRate API key not configured.")
         return None
    # Using USD as target is common, or you could let AI specify or use a default
    target_currency_code = "USD" # Default target
    try:
        # Check if base is a valid currency code (basic check)
        if len(base_currency_code) != 3 or not base_currency_code.isalpha():
            print(f"Invalid base currency code: {base_currency_code}")
            # Attempt to find the target currency code in the query if base is invalid
            # This is a very basic fallback; a real implementation needs better parsing or AI help
            if isinstance(request.json.get('message'), str):
                import re
                match = re.search(r'to ([A-Z]{3})', request.json.get('message').upper())
                if match:
                    target_currency_code = match.group(1)
                    print(f"Found potential target currency '{target_currency_code}' from query.")
                else:
                     # If no target found, maybe try a common default like VND or keep USD
                     pass # Keep USD as default target

        api_url = f"{EXCHANGERATE_API_URL}{EXCHANGERATE_API_KEY}/latest/{base_currency_code.upper()}"
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        if data and data.get('result') == 'success' and 'conversion_rates' in data:
            if target_currency_code in data['conversion_rates']:
                 rate = data['conversion_rates'][target_currency_code]
                 return {"base": base_currency_code.upper(), "target": target_currency_code, "rate": rate}
            else:
                 print(f"Target currency {target_currency_code} not found in rates for {base_currency_code}. Available: {list(data['conversion_rates'].keys())}")
                 # Fallback: return rate against USD if available, or the whole conversion_rates dict
                 if "USD" in data['conversion_rates'] and target_currency_code != "USD":
                      print(f"Falling back to USD rate for {base_currency_code}.")
                      return {"base": base_currency_code.upper(), "target": "USD", "rate": data['conversion_rates']["USD"], "note": f"Tỷ giá so với {target_currency_code} không có sẵn, hiển thị tỷ giá so với USD."}
                 # If USD also not available, maybe list a few common ones?
                 common_targets = ['VND', 'EUR', 'GBP', 'JPY', 'CAD']
                 available_rates = {k: v for k, v in data['conversion_rates'].items() if k in common_targets or k == base_currency_code.upper() or len(available_rates) < 5} # Get up to 5 rates including base/common
                 print(f"Could not get target currency {target_currency_code} or USD. Returning some available rates.")
                 return {"base": base_currency_code.upper(), "rates": available_rates, "note": f"Không thể lấy tỷ giá chính xác, đây là một số tỷ giá phổ biến so với {base_currency_code.upper()}."}


        else:
             print(f"Could not get exchange rate for {base_currency_code}. Data: {data}")
             return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching exchange rate for {base_currency_code}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing exchange rate data: {e}")
        return None


def get_news_data(country_name):
    """Fetches news headlines for a country using NewsAPI."""
    if not NEWSAPI_API_KEY:
        print("NewsAPI key not configured.")
        return None
    try:
        # NewsAPI expects a 2-letter country code.
        # We need to map country name to code. restcountries data can provide this.
        # For simplicity here, let's try to find the country code first using restcountries.
        country_data = get_country_data(country_name)
        country_code = country_data['cca2'].lower() if country_data and 'cca2' in country_data else None

        if not country_code:
            print(f"Could not determine country code for news search for {country_name}")
            return None

        # NewsAPI has limitations on free tier (e.g., cannot search everything, only headlines from specific sources/countries)
        # Using 'top-headlines' is usually better for a country feed on free tier.
        # url = f'{NEWSAPI_API_URL}q={requests.utils.quote(country_name)}&apiKey={NEWSAPI_API_KEY}&language=en' # Use 'everything' but free tier is limited
        url = f'https://newsapi.org/v2/top-headlines?country={country_code}&apiKey={NEWSAPI_API_KEY}' # Using top-headlines by country code
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data and data.get('status') == 'ok' and data.get('articles'):
            # Return top few articles
            return data['articles'][:5] # Get top 5 articles
        else:
            print(f"No news found or error from NewsAPI for {country_name} ({country_code}). Data: {data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching news data for {country_name}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing news data: {e}")
        return None


# --- AI Prompting Logic within the chat route ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)


@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"reply": "Vui lòng nhập câu hỏi."})

    print(f"Received message: {user_message}")

    if not model:
         return jsonify({"reply": "Xin lỗi, hệ thống AI hiện không khả dụng. Vui lòng kiểm tra cấu hình GOOGLE_API_KEY."})

    # Step 1: Use AI to analyze intent and entities
    # Added instruction to avoid markdown bold
    ai_analysis_prompt = f"""Phân tích câu hỏi của người dùng: "{user_message}"
    Xác định ý định chính (Intent) của người dùng và các thực thể (Entity) liên quan.
    Các ý định chính có thể là:
    - get_country_info: Hỏi thông tin cơ bản về một quốc gia (dân số, thủ đô, diện tích, ngôn ngữ...).
    - compare_countries: So sánh thông tin giữa các quốc gia (cần 2 quốc gia).
    - get_weather: Hỏi thời tiết của một quốc gia hoặc thành phố (cần quốc gia/thành phố).
    - get_exchange_rate: Hỏi tỷ giá hối đoái liên quan đến một quốc gia hoặc cặp tiền tệ (cần quốc gia hoặc cặp tiền tệ).
    - get_news: Hỏi tin tức về một quốc gia (cần quốc gia).
    - travel_recommendation: Yêu cầu gợi ý du lịch (cần sở thích/tiêu chí).
    - general_chat: Câu hỏi chào hỏi, cảm ơn, hoặc không thuộc các loại trên.

    Các thực thể cần trích xuất:
    - country: Tên quốc gia. Có thể là 1 tên (cho get_country_info, get_weather, get_news, get_exchange_rate) hoặc một mảng 2 tên (cho compare_countries). Nếu là thành phố, vẫn trích xuất vào đây và ghi chú (ví dụ: "Tokyo (thành phố)").
    - criteria: Tiêu chí cụ thể được hỏi (ví dụ: dân số, GDP, thủ đô, nhiệt độ, cặp tiền tệ). Chỉ trích xuất nếu người dùng hỏi cụ thể.
    - preferences: Thông tin về sở thích du lịch, ngân sách, thời gian đi (for travel_recommendation). Trích xuất nguyên văn nếu có.
    - currency: Mã tiền tệ (ví dụ: "VND", "USD") hoặc tên tiền tệ nếu người dùng hỏi về tỷ giá.

    Trả về kết quả dưới dạng JSON. Nếu không chắc chắn hoặc không trích xuất được entity cần thiết cho intent, dùng general_chat. Tên quốc gia nên được chuẩn hóa nếu có thể (ví dụ: "VN" -> "Việt Nam").

    Ví dụ Output JSON:
    {{ "intent": "get_country_info", "entities": {{ "country": "Việt Nam", "criteria": "dân số" }} }}
    {{ "intent": "compare_countries", "entities": {{ "country": ["Pháp", "Đức"], "criteria": "GDP" }} }}
    {{ "intent": "get_weather", "entities": {{ "country": "London (thành phố)" }} }}
    {{ "intent": "get_exchange_rate", "entities": {{ "currency": "VND to USD" }} }}
    {{ "intent": "travel_recommendation", "entities": {{ "preferences": "du lịch biển ở châu Á, ngân sách vừa phải" }} }}
    {{ "intent": "general_chat", "entities": {{}} }}

    Chỉ trả về JSON, không thêm bất kỳ văn bản giải thích nào khác.
    """
    try:
        analysis_response = model.generate_content(ai_analysis_prompt)
        # Clean up the JSON string
        json_string = analysis_response.text.strip()
        # Handle cases where AI wraps JSON in markdown
        if json_string.startswith("```json"):
            json_string = json_string[7:-3].strip()
        elif json_string.startswith("```"): # Handle generic markdown block
             json_string = json_string[3:-3].strip()
        # Remove trailing commas that sometimes appear before closing brackets/braces
        json_string = re.sub(r',(\s*[}\]])', r'\1', json_string)


        ai_analysis = json.loads(json_string)
        print(f"AI Analysis: {ai_analysis}")

        intent = ai_analysis.get("intent")
        entities = ai_analysis.get("entities", {})
        country_names = entities.get("country") # Could be string or list
        criteria = entities.get("criteria")
        preferences = entities.get("preferences")
        currency_query = entities.get("currency") # Use currency query from AI analysis
        currency_code_from_country = None # To store currency code if identified via country

        bot_reply = "Xin lỗi, tôi gặp khó khăn khi xử lý yêu cầu của bạn."
        country_latlng = None # To be sent back for map control
        identified_country_name = None # To be sent back for map popup name

        # Step 2: Act based on intent and call APIs
        if intent == "get_country_info" and country_names:
            # Assume country_names is a string for this intent
            country_name = country_names if isinstance(country_names, str) else country_names[0] if isinstance(country_names, list) and country_names else None
            if country_name:
                country_data = get_country_data(country_name)
                if country_data:
                     # Pass data to AI for formatting the info
                     # *** UPDATED PROMPT ***
                     format_prompt = f"""Người dùng hỏi thông tin về quốc gia {country_name}.
                     Đây là dữ liệu chi tiết về quốc gia (định dạng JSON): {json.dumps(country_data, ensure_ascii=False, indent=2)}
                     Dựa vào dữ liệu trên, hãy trả lời câu hỏi của người dùng một cách tự nhiên bằng Tiếng Việt.
                     **Trình bày các thông tin thành từng dòng sử dụng gạch đầu dòng (-) hoặc danh sách có cấu trúc.**
                     Không sử dụng định dạng in đậm markdown (**).
                     Nếu người dùng hỏi về một tiêu chí cụ thể ("{criteria}"), hãy tập trung vào đó và trình bày rõ ràng.
                     Nếu không, hãy cung cấp một bản tóm tắt thông tin cơ bản (thủ đô, dân số, diện tích, ngôn ngữ chính) dưới dạng danh sách gạch đầu dòng.
                     Nếu không tìm thấy thông tin cần thiết trong dữ liệu, hãy nói rõ.
                     """
                     try:
                        formatted_response = model.generate_content(format_prompt)
                        bot_reply = formatted_response.text
                        # Get coordinates for map
                        if 'latlng' in country_data and len(country_data['latlng']) == 2:
                            country_latlng = country_data['latlng']
                            identified_country_name = country_data['name']['common'] # Use common name for popup
                        elif 'capitalInfo' in country_data and 'latlng' in country_data['capitalInfo'] and len(country_data['capitalInfo']['latlng']) == 2:
                             country_latlng = country_data['capitalInfo']['latlng']
                             identified_country_name = country_data['name']['common'] # Use common name for popup
                     except Exception as e:
                         print(f"Error formatting country info response with AI: {e}")
                         bot_reply = f"Tôi đã tìm thấy dữ liệu về {country_name} nhưng gặp khó khăn khi tóm tắt. Vui lòng hỏi lại."
                         # Fallback: provide raw data or basic info if AI fails
                         if country_data:
                             capital = ', '.join(country_data.get('capital', ['N/A']))
                             population = f"{country_data.get('population', 'N/A'):,}".replace(',', '.') # Format population with dots
                             area = f"{country_data.get('area', 'N/A'):,}".replace(',', '.') # Format area with dots
                             languages = ', '.join(country_data.get('languages', {}).values()) if country_data.get('languages') else 'N/A'

                             bot_reply += f"\n- Thủ đô: {capital}\n- Dân số: {population}\n- Diện tích: {area} km²\n- Ngôn ngữ chính: {languages}" # Use '-' in fallback too


                else:
                    bot_reply = f"Xin lỗi, tôi không tìm thấy thông tin về quốc gia {country_name}."

        elif intent == "compare_countries" and isinstance(country_names, list) and len(country_names) == 2:
             country1_name = country_names[0]
             country2_name = country_names[1]
             country1_data = get_country_data(country1_name)
             country2_data = get_country_data(country2_name)

             if country1_data and country2_data:
                  # Pass data to AI for comparison text generation
                  # *** UPDATED PROMPT ***
                  compare_prompt = f"""Người dùng muốn so sánh {country1_name} và {country2_name} dựa trên tiêu chí {criteria if criteria else 'tổng quát (dân số, thủ đô, diện tích, ngôn ngữ, GDP ước tính nếu có)'}.
                  Đây là dữ liệu của {country1_name} (JSON): {json.dumps(country1_data, ensure_ascii=False, indent=2)}
                  Đây là dữ liệu của {country2_data} (JSON): {json.dumps(country2_data, ensure_ascii=False, indent=2)}
                  Hãy tạo một đoạn văn bản so sánh hai quốc gia này dựa trên dữ liệu được cung cấp và tiêu chí yêu cầu (hoặc so sánh tổng quát nếu không có tiêu chí cụ thể).
                  **Trình bày kết quả so sánh một cách rõ ràng, sử dụng gạch đầu dòng (-) hoặc bảng đơn giản nếu phù hợp.**
                  Không sử dụng định dạng in đậm markdown (**).
                  Nếu không có dữ liệu cho một tiêu chí nào đó, hãy bỏ qua hoặc nói rõ.
                  Trả lời bằng Tiếng Việt.
                  """
                  try:
                      comparison_response = model.generate_content(compare_prompt)
                      bot_reply = comparison_response.text
                      # No single coordinate for comparison, don't set country_latlng
                  except Exception as e:
                      print(f"Error generating comparison with AI: {e}")
                      bot_reply = f"Tôi gặp khó khăn khi so sánh {country1_name} và {country2_name} lúc này."
             elif country1_data:
                 bot_reply = f"Tôi tìm thấy thông tin về {country1_name} nhưng không tìm thấy về {country2_name}. Vui lòng kiểm tra lại tên quốc gia thứ hai."
             elif country2_data:
                 bot_reply = f"Tôi tìm thấy thông tin về {country2_name} nhưng không tìm thấy về {country1_name}. Vui lòng kiểm tra lại tên quốc gia thứ nhất."
             else:
                 bot_reply = f"Tôi không tìm thấy thông tin về cả hai quốc gia {country1_name} và {country2_name}. Vui lòng kiểm tra lại tên."

        elif intent == "get_weather" and country_names: # Can be country or city
            # Assume country_names is a string (could be city)
            location_name = country_names if isinstance(country_names, str) else country_names[0] if isinstance(country_names, list) and country_names else None

            if location_name:
                 # First, try to get coordinates. If it's a country, use capital coords.
                 # If it's likely a city, you might need a geocoding API (more complex).
                 # For simplicity with restcountries, let's try getting country data first.
                 country_data = get_country_data(location_name) # Try treating it as a country
                 latlng = None
                 display_name = location_name # Default display name

                 if country_data and 'capitalInfo' in country_data and 'latlng' in country_data['capitalInfo'] and len(country_data['capitalInfo']['latlng']) == 2:
                      latlng = country_data['capitalInfo']['latlng']
                      display_name = country_data['capital'][0] if country_data.get('capital') else country_data['name']['common'] + ' (Thủ đô)' # Use capital name if available
                      identified_country_name = country_data['name']['common'] # Use common name for popup
                 elif country_data and 'latlng' in country_data and len(country_data['latlng']) == 2:
                      latlng = country_data['latlng'] # Use country center coords if capital coords missing
                      display_name = country_data['name']['common'] + ' (Trung tâm)'
                      identified_country_name = country_data['name']['common'] # Use common name for popup
                 else:
                      # If not found as a country or no coords, treat as city? Needs geocoding.
                      # Placeholder: Assume a city might be searched directly, but Restcountries won't find it.
                      # In a real app, you'd call a geocoding service like Nominatim or Google Geocoding API here.
                      print(f"Could not find coordinates for {location_name} using Restcountries. Geocoding needed.")
                      bot_reply = f"Xin lỗi, tôi không tìm thấy vị trí '{location_name}' để lấy thông tin thời tiết."


                 if latlng:
                     weather_data = get_weather_data(latlng[0], latlng[1])
                     if weather_data:
                          # Pass data to AI for formatting
                          # *** UPDATED PROMPT ***
                         weather_prompt = f"""Người dùng hỏi thời tiết tại {display_name}.
                         Đây là dữ liệu thời tiết (JSON) cho vị trí này: {json.dumps(weather_data, ensure_ascii=False, indent=2)}
                         Dựa vào dữ liệu trên, hãy trả lời về thời tiết hiện tại tại {display_name} một cách tự nhiên bằng Tiếng Việt.
                         **Trình bày các thông tin thành từng dòng sử dụng gạch đầu dòng (-).**
                         Không sử dụng định dạng in đậm markdown (**).
                         Bao gồm mô tả, nhiệt độ, cảm giác thực, độ ẩm, tốc độ gió.
                         Nếu dữ liệu bị thiếu, nói rõ hoặc bỏ qua phần đó.
                         """
                         try:
                            weather_response = model.generate_content(weather_prompt)
                            bot_reply = weather_response.text
                            # Set map coordinates to the location found (capital or country center)
                            country_latlng = latlng
                            # identified_country_name might already be set if it was a country

                         except Exception as e:
                             print(f"Error formatting weather response with AI: {e}")
                             bot_reply = f"Tôi đã tìm thấy dữ liệu thời tiết cho {display_name} nhưng gặp khó khăn khi tóm tắt."
                             if weather_data: # Fallback
                                 bot_reply += f"\n- Thời tiết: {weather_data.get('description', 'N/A')}\n- Nhiệt độ: {weather_data.get('temp', 'N/A')}°C\n- Độ ẩm: {weather_data.get('humidity', 'N/A')}%\n- Gió: {weather_data.get('wind_speed', 'N/A')} m/s." # Use '-' in fallback too
                             country_latlng = latlng # Still set coords for map

                     else:
                         bot_reply = f"Xin lỗi, tôi không thể lấy thông tin thời tiết cho '{display_name}' lúc này. Vui lòng thử lại sau."
                         # If country data was found but weather failed, still center map
                         if latlng:
                             country_latlng = latlng


        elif intent == "get_exchange_rate":
             # Try to get currency code first from country name found by AI
             country_name = entities.get("country")
             currency_code = None # Initialize currency_code

             if country_name:
                 # Ensure country_name is a string if it came as a list
                 country_name_str = country_name if isinstance(country_name, str) else country_name[0] if isinstance(country_name, list) and country_names else None
                 if country_name_str:
                    country_data = get_country_data(country_name_str)
                    if country_data and country_data.get('currencies'):
                        # Get the first currency code associated with the country
                        currency_code = list(country_data['currencies'].keys())[0]
                        identified_country_name = country_data['name']['common'] # Use common name for popup

             # If currency code wasn't found via country, try parsing the currency_query directly
             if not currency_code and isinstance(currency_query, str):
                 # Basic attempt to find 3-letter code in query (case-insensitive)
                 match = re.search(r'\b([A-Za-z]{3})\b', currency_query)
                 if match:
                      currency_code = match.group(1).upper()
                      print(f"Identified currency code '{currency_code}' from query string.")

             if currency_code:
                 exchange_data = get_exchange_rate(currency_code)
                 if exchange_data:
                     # Pass data to AI for formatting
                     # *** UPDATED PROMPT ***
                     exchange_prompt = f"""Người dùng hỏi về tỷ giá hối đoái.
                     Đây là dữ liệu tỷ giá (JSON): {json.dumps(exchange_data, ensure_ascii=False, indent=2)}
                     Dựa vào dữ liệu trên, hãy trả lời về tỷ giá hối đoái một cách tự nhiên bằng Tiếng Việt.
                     **Trình bày thông tin tỷ giá thành từng dòng sử dụng gạch đầu dòng (-).**
                     Không sử dụng định dạng in đậm markdown (**).
                     Nếu dữ liệu chứa tỷ giá cho một cặp cụ thể (ví dụ: 1 USD = X VND), hãy nói rõ tỷ giá đó.
                     Nếu dữ liệu chứa nhiều tỷ giá (ví dụ: so với nhiều tiền tệ phổ biến), hãy liệt kê một vài tỷ giá chính dưới dạng danh sách.
                     Nói rõ 1 đơn vị tiền tệ cơ sở tương đương bao nhiêu đơn vị tiền tệ mục tiêu hoặc các tiền tệ khác được liệt kê.
                     """
                     try:
                        exchange_response = model.generate_content(exchange_prompt)
                        bot_reply = exchange_response.text
                     except Exception as e:
                         print(f"Error formatting exchange rate response with AI: {e}")
                         # Fallback: Format based on the structure of exchange_data
                         if 'rate' in exchange_data and 'target' in exchange_data:
                              bot_reply = f"- Tỷ giá hiện tại: 1 {exchange_data.get('base', 'N/A')} = {exchange_data.get('rate', 'N/A'):.4f} {exchange_data.get('target', 'N/A')}." # Use '-' in fallback too
                              if 'note' in exchange_data: bot_reply += f" ({exchange_data['note']})"
                         elif 'rates' in exchange_data:
                              bot_reply = f"Một số tỷ giá phổ biến so với 1 {exchange_data.get('base', 'N/A')}:\n"
                              for target, rate in exchange_data['rates'].items():
                                   bot_reply += f"- {target}: {rate:.4f}\n" # Use '-' in fallback too
                              if 'note' in exchange_data: bot_reply += f" ({exchange_data['note']})"
                         else:
                             bot_reply = "Không có dữ liệu tỷ giá chi tiết để hiển thị."


                 else:
                      bot_reply = f"Xin lỗi, tôi không thể lấy thông tin tỷ giá hối đoái cho '{currency_code}' lúc này. Vui lòng thử lại sau."
             elif not currency_query and not country_name: # If AI didn't identify either
                  bot_reply = "Vui lòng cho tôi biết quốc gia hoặc loại tiền tệ bạn muốn hỏi về tỷ giá."
             elif currency_query and not currency_code: # If AI identified query but we couldn't parse a code
                  bot_reply = f"Tôi không chắc chắn về loại tiền tệ bạn hỏi ('{currency_query}'). Vui lòng thử lại với mã tiền tệ 3 chữ cái hoặc tên quốc gia."
             # else: if country_name found but no currency code, bot_reply already set above


        elif intent == "get_news" and country_names:
            # Assume country_names is a string
            country_name = country_names if isinstance(country_names, str) else country_names[0] if isinstance(country_names, list) and country_names else None
            if country_name:
                news_articles = get_news_data(country_name)
                if news_articles:
                    # Pass data to AI for formatting
                    # *** UPDATED PROMPT ***
                    news_prompt = f"""Người dùng hỏi về tin tức mới nhất cho quốc gia {country_name}.
                    Đây là danh sách các bài báo (JSON): {json.dumps(news_articles, ensure_ascii=False, indent=2)}
                    Dựa vào dữ liệu trên, hãy tóm tắt và liệt kê các tin tức mới nhất cho {country_name} một cách tự nhiên bằng Tiếng Việt.
                    **Trình bày dưới dạng danh sách gạch đầu dòng (-).**
                    Không sử dụng định dạng in đậm markdown (**).
                    Chỉ cần liệt kê tiêu đề và liên kết của một vài bài chính (khoảng 3-5 bài).
                    """
                    try:
                        news_response = model.generate_content(news_prompt)
                        bot_reply = news_response.text
                        # Get coordinates for map if country data was found
                        country_data = get_country_data(country_name)
                        if country_data and 'latlng' in country_data and len(country_data['latlng']) == 2:
                           country_latlng = country_data['latlng']
                           identified_country_name = country_data['name']['common'] # Use common name for popup

                    except Exception as e:
                         print(f"Error formatting news response with AI: {e}")
                         bot_reply = f"Tôi đã tìm thấy tin tức cho {country_name} nhưng gặp khó khăn khi tóm tắt. Dưới đây là một số tiêu đề gốc:"
                         # Fallback: List titles and URLs directly
                         for article in news_articles[:5]:
                             bot_reply += f"\n- {article.get('title', 'Không tiêu đề')}: {article.get('url', 'Không link')}" # Use '-' in fallback too


                else:
                    bot_reply = f"Xin lỗi, tôi không tìm thấy tin tức mới cho quốc gia {country_name} lúc này."
                    # If country data was found but news failed, still center map
                    country_data = get_country_data(country_name)
                    if country_data and 'latlng' in country_data and len(country_data['latlng']) == 2:
                       country_latlng = country_data['latlng']
                       identified_country_name = country_data['name']['common']

        elif intent == "travel_recommendation" and preferences:
             # Pass preferences to AI for recommendation generation
             # *** UPDATED PROMPT ***
             recommend_prompt = f"""Người dùng muốn gợi ý du lịch dựa trên sở thích: "{preferences}".
             Hãy đóng vai trò là một chuyên gia tư vấn du lịch AI.
             **Trình bày các gợi ý dưới dạng danh sách gạch đầu dòng (-), mỗi mục là một gợi ý địa điểm.**
             Không sử dụng định dạng in đậm markdown (**).
             Dựa trên sở thích này, hãy gợi ý một vài quốc gia hoặc khu vực phù hợp.
             Nêu bật lý do tại sao những nơi đó phù hợp (ví dụ: có biển đẹp, phong cảnh núi non, lịch sử phong phú, chi phí hợp lý...).
             Cung cấp thông tin ngắn gọn về mỗi điểm đến được gợi ý.
             Trả lời một cách tự nhiên, thân thiện bằng Tiếng Việt.
             """
             try:
                 recommendation_response = model.generate_content(recommend_prompt)
                 bot_reply = recommendation_response.text
                 # No specific country coordinate to set for a general recommendation

             except Exception as e:
                 print(f"Error generating travel recommendation with AI: {e}")
                 bot_reply = f"Tôi gặp khó khăn khi tạo gợi ý du lịch dựa trên sở thích của bạn lúc này."


        elif intent == "general_chat":
             # If it's general chat, just pass the message to AI with a general persona prompt
             # *** UPDATED PROMPT ***
             general_prompt = f"Bạn là một trợ lý AI thân thiện chuyên về thông tin quốc gia, được tạo bởi Google AI. Người dùng nói: \"{user_message}\". Hãy trả lời một cách thân thiện bằng Tiếng Việt. **Nếu bạn liệt kê nhiều điểm, hãy sử dụng gạch đầu dòng (-).** Không sử dụng định dạng in đậm markdown (**)."
             try:
                 general_response = model.generate_content(general_prompt)
                 bot_reply = general_response.text
             except Exception as e:
                 print(f"Error generating general chat response: {e}")
                 bot_reply = "Xin chào! Tôi có thể giúp gì cho bạn về các quốc gia?"
             # No specific country coordinate for general chat


        else:
            # If intent not recognized or entities missing, fall back to general chat
            print(f"Intent '{intent}' not handled or entities missing for message: {user_message}")
            # *** UPDATED PROMPT ***
            fallback_prompt = f"Bạn là một trợ lý AI thân thiện chuyên về thông tin quốc gia. Người dùng nói: \"{user_message}\". Tôi không chắc chắn ý của bạn. Hãy trả lời một cách thân thiện bằng Tiếng Việt và hỏi lại xem bạn có thể giúp gì về các quốc gia. **Nếu bạn liệt kê nhiều điểm, hãy sử dụng gạch đầu dòng (-).** Không sử dụng định dạng in đậm markdown (**)."
            try:
                fallback_response = model.generate_content(fallback_prompt)
                bot_reply = fallback_response.text
            except Exception as e:
                 print(f"Error generating fallback response: {e}")
                 bot_reply = "Xin lỗi, tôi không hiểu yêu cầu của bạn. Tôi có thể giúp gì về các quốc gia?"


    except json.JSONDecodeError:
        print(f"AI analysis response was not valid JSON: {analysis_response.text}")
        # Fallback: Just send original message to AI as general chat
        print("Falling back to general chat due to JSON error.")
        # *** UPDATED PROMPT ***
        general_prompt = f"Bạn là một trợ lý AI thân thiện chuyên về thông tin quốc gia, được tạo bởi Google AI. Người dùng nói: \"{user_message}\". Hãy trả lời một cách thân thiện bằng Tiếng Việt. **Nếu bạn liệt kê nhiều điểm, hãy sử dụng gạch đầu dòng (-).** Không sử dụng định dạng in đậm markdown (**)."
        try:
            general_response = model.generate_content(general_prompt)
            bot_reply = general_response.text
        except Exception as e:
            print(f"Error handling JSON error with fallback AI call: {e}")
            bot_reply = "Xin lỗi, có lỗi xảy ra khi phân tích yêu cầu của bạn."

    except Exception as e:
        print(f"An unexpected error occurred during chat processing: {e}")
        bot_reply = "Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu của bạn."

    # --- Final Cleanup: Attempt to remove remaining markdown bold from AI reply ---
    # This is a safety measure in case the AI instruction isn't perfectly followed.
    # Use regex to remove ** surrounding text or just standalone **
    bot_reply = re.sub(r'\*\*(.*?)\*\*', r'\1', bot_reply) # Remove ** surrounding text, keep text
    bot_reply = bot_reply.replace('**', '') # Remove any remaining standalone **

    # --- Database: Log history (simplified) ---
    # In a real app, you'd save user_message and bot_reply to a database
    print(f"Logging search: User='{user_message}', Bot='{bot_reply[:150]}...'")

    # Return the reply and optional data for frontend (like coordinates)
    response_data = {"reply": bot_reply}
    if country_latlng:
        response_data["country_latlng"] = country_latlng
        response_data["country_name"] = identified_country_name # Include common name for popup

    return jsonify(response_data)


# --- Add other API endpoints for History and Favorites (Database needed) ---
# Note: The frontend history is now using in-memory data.
# If you implement backend history, you'll need these endpoints:
# @app.route('/history')
# def get_history():
#     # Fetch history from DB and return JSON list [{query: "..."}]
#     return jsonify([]) # Placeholder

# @app.route('/add-history', methods=['POST'])
# def add_history():
#     # Add {query: "...", reply: "..."} to history in DB
#     # This would be called after a successful chat exchange
#     return jsonify({"success": True}) # Placeholder


# --- Run the Flask app ---
if __name__ == '__main__':
    # Check for API keys on startup (basic check)
    if not GOOGLE_API_KEY:
        print("Warning: GOOGLE_API_KEY not set. AI chat will not work.")
    if not OPENWEATHERMAP_API_KEY:
         print("Warning: OPENWEATHERMAP_API_KEY not set. Weather feature will not work.")
    if not EXCHANGERATE_API_KEY:
         print("Warning: EXCHANGERATE_API_KEY not set. Exchange rate feature will not work.")
    if not NEWSAPI_API_KEY:
         print("Warning: NEWSAPI_API_KEY not set. News feature will not work.")

    # Make sure index.html and static files are in the same directory
    app.run(debug=True) # debug=True is for development only