from sqlalchemy.orm import Session
from database import SessionLocal
from models import SATExampleCorpus

# Mở kết nối
db = SessionLocal()

try:
    print("Đang xóa kết quả chấm cũ...")
    
    # Lệnh update update toàn bộ bảng, set các cột điểm về NULL
    num_rows = db.query(SATExampleCorpus).update({
        SATExampleCorpus.predicted_score: None,
        SATExampleCorpus.predicted_difficulty: None,
        SATExampleCorpus.llm_reasoning: None
    })
    
    db.commit()
    print(f"✅ Đã xóa điểm của {num_rows} câu hỏi. Database đã sạch để chấm lại!")

except Exception as e:
    print(f"❌ Lỗi: {e}")
    db.rollback()
finally:
    db.close()