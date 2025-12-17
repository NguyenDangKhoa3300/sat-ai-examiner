# database.py (SECURE VERSION)

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 1. Load biến môi trường từ file .env (chỉ chạy ở Local)
load_dotenv()

# 2. Lấy địa chỉ DB từ biến môi trường
# Nếu không tìm thấy (ví dụ quên tạo file .env), nó sẽ báo lỗi hoặc trả về None
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is missing! Please check your .env file.")

# *FIX CHO RENDER/HEROKU*: 
# Các server này thường trả về chuỗi bắt đầu bằng 'postgres://', 
# nhưng SQLAlchemy cần 'postgresql://'. Dòng này sẽ tự sửa lỗi đó.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Tạo Engine
engine = create_engine(DATABASE_URL)

# 4. Tạo Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Base Class
Base = declarative_base()

def get_db():
    """Hàm tiện ích để tạo và đóng DB Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()