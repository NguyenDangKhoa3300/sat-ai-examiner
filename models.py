# models.py (FINAL VERSION with LLM Result Columns and Expert Score Band)

from sqlalchemy import Column, Integer, String, Text
# Không cần declarative_base ở đây nếu nó đã được định nghĩa trong database.py

# Đảm bảo bạn sử dụng direct import nếu các file khác nằm trong cùng thư mục
from database import Base 

class SATExampleCorpus(Base):
    """Bảng lưu trữ câu hỏi SAT, nhãn chuyên gia (bao gồm Score Band) và kết quả LLM."""
    __tablename__ = 'sat_example_corpus'

    # Dữ liệu từ Scraping (Input & Gold Label)
    id = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    correct_answer = Column(String, nullable=True) 
    parent_topic = Column(String, nullable=False)
    child_topic = Column(String, nullable=False)
    expert_difficulty = Column(String, nullable=False) # E, M, H (Gold Label)
    expert_notes = Column(Text, nullable=True)
    
    # CỘT MỚI: Score Band từ trang web (ví dụ: 1, 2, 3, 4)
    expert_score_band = Column(Integer, nullable=True) 

    # Dữ liệu Kết quả LLM (Predicted Labels)
    predicted_difficulty = Column(String, nullable=True) # Easy, Medium, Hard
    llm_reasoning = Column(Text, nullable=True)
    predicted_score = Column(Integer, nullable=True)