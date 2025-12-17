# config.py (FINAL SECURE VERSION)

import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# 1. Tải biến môi trường từ file .env
load_dotenv()

# 2. Lấy API Key từ hệ thống (An toàn)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 3. Kiểm tra bảo mật (QUAN TRỌNG)
if not GEMINI_API_KEY:
    # Nếu không tìm thấy Key, dừng chương trình ngay lập tức để báo lỗi
    # TUYỆT ĐỐI KHÔNG điền key cứng vào đây (Hardcode) nếu bạn định up lên GitHub
    print("❌ CRITICAL ERROR: API Key is missing!")
    print("👉 Please create a '.env' file and add GEMINI_API_KEY=...")
    sys.exit(1) # Dừng server lại

# 4. Cấu hình thư viện Gemini
genai.configure(api_key=GEMINI_API_KEY)

# --- MODEL CONFIGURATION ---
# Lưu ý: "gemini-2.0-flash" có thể cần dùng bản experiment là "gemini-2.0-flash-exp"
# Nếu bản 2.0 chưa public rộng rãi, hãy dùng "gemini-1.5-flash" cho ổn định.
GEMINI_MODEL_NAME = "gemini-2.0-flash-exp" 

# --- GENERATION CONFIG ---
# Tôi đã tăng max_output_tokens lên 2048 vì phần giải thích (Reasoning)
# đôi khi khá dài, 1024 có thể bị cắt giữa chừng.
GENERATION_CONFIG = {
    "temperature": 0.1,  # Giữ thấp để AI tập trung giải toán, bớt sáng tạo linh tinh
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048, 
    "response_mime_type": "application/json", 
}