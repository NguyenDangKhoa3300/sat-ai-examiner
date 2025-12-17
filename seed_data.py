# seed_data.py (FINAL VERSION - Auto Reset & Robust Loading)

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import SATExampleCorpus
from database import SessionLocal, engine, Base

# --- Dữ liệu mẫu (Minimal Few-shot) ---
# Giữ lại để đảm bảo hệ thống có dữ liệu khởi động cho Few-shot learning
SAT_EXAMPLES_DATA = [
    {
        "question_text": "The dog ran quickly to the park, and it chased the ball.",
        "option_a": "The dog ran quickly to the park, and it chased the ball.",
        "option_b": "The dog, ran quickly to the park and chased the ball.",
        "option_c": "The dog ran quickly, to the park and chased the ball.",
        "option_d": "The dog ran quickly to the park; and it chased the ball.",
        "correct_answer": "A",
        "parent_topic": "Standard English Conventions",
        "child_topic": "Boundaries",
        "expert_difficulty": "Easy",
        "expert_score_band": 2, 
        "expert_notes": "Simple comma rule for coordinating conjunction."
    },
    {
        "question_text": "Which choice best describes the main purpose of the text?",
        "option_a": "To argue for increased funding for space exploration.",
        "option_b": "To outline the historical development of a scientific theory.",
        "option_c": "To challenge conventional views on planetary motion.",
        "option_d": "To introduce new data supporting a previously rejected hypothesis.",
        "correct_answer": "B",
        "parent_topic": "Information and Ideas",
        "child_topic": "Central Ideas and Details",
        "expert_difficulty": "Medium",
        "expert_score_band": 5, 
        "expert_notes": "Requires synthesizing the central idea from the first and last paragraphs."
    },
    {
        "question_text": "The writer wants to connect the paragraph's claim about quantum entanglement to the main argument about information transfer. Which choice best accomplishes this goal?",
        "option_a": "Therefore, entanglement remains a puzzle for physicists.",
        "option_b": "This entanglement, however, does not allow for faster-than-light communication.",
        "option_c": "Researchers have not yet found a way to leverage entanglement.",
        "option_d": "The concept of entanglement was first proposed by Einstein.",
        "correct_answer": "B",
        "parent_topic": "Expression of Ideas",
        "child_topic": "Transitions",
        "expert_difficulty": "Hard",
        "expert_score_band": 7, 
        "expert_notes": "All options are plausible, but only B correctly addresses the complex rhetorical link (entanglement vs. information transfer)."
    },
]

def reset_database():
    """Xóa bảng cũ để đảm bảo dữ liệu mới được nạp sạch sẽ."""
    print("WARNING: Resetting database tables...")
    try:
        # Xóa bảng nếu tồn tại
        SATExampleCorpus.__table__.drop(engine)
        print("Dropped table 'sat_example_corpus'.")
    except Exception as e:
        print(f"Table might not exist, skipping drop: {e}")
    
    # Tạo lại bảng mới với cấu trúc cập nhật nhất (từ models.py)
    Base.metadata.create_all(bind=engine)
    print("Re-created all tables successfully.")

def load_initial_data(db: Session):
    """Loads minimal few-shot examples into DB."""
    print("Loading minimal SAT Examples (Seed Data)...")
    count = 0
    for data in SAT_EXAMPLES_DATA:
        # Kiểm tra trùng lặp (dù mới reset nhưng giữ logic này cho an toàn)
        if not db.query(SATExampleCorpus).filter(SATExampleCorpus.question_text == data["question_text"]).first():
            db.add(SATExampleCorpus(**data))
            count += 1
    db.commit()
    print(f"Loaded {count} seed examples.")

def load_scraped_data(db: Session, file_path: str):
    """Loads scraped questions from CSV into SATExampleCorpus."""
    print(f"Loading scraped data from {file_path}...")
    
    try:
        # Load CSV
        df = pd.read_csv(file_path)
        
        # Kiểm tra cột bắt buộc
        required_cols = ['question_text', 'expert_difficulty', 'expert_score_band']
        for col in required_cols:
            if col not in df.columns:
                print(f"ERROR: Missing required column '{col}' in CSV.")
                return

        # Xử lý NaN
        df['correct_answer'] = df['correct_answer'].fillna('')
        df = df.replace({np.nan: None}) # Thay thế toàn bộ NaN bằng None để SQL hiểu
        
        count = 0
        skipped = 0
        
        for index, row in df.iterrows():
            # Kiểm tra trùng lặp với dữ liệu seed hoặc dữ liệu đã nạp
            if db.query(SATExampleCorpus).filter(SATExampleCorpus.question_text == row["question_text"]).first():
                skipped += 1
                continue

            # Xử lý Score Band an toàn
            score_band = row.get("expert_score_band")
            if score_band is not None:
                try:
                    score_band = int(float(score_band))
                except:
                    score_band = None

            question = SATExampleCorpus(
                question_text=row["question_text"],
                option_a=row["option_a"],
                option_b=row["option_b"],
                option_c=row["option_c"],
                option_d=row["option_d"],
                correct_answer=row["correct_answer"],
                parent_topic=row["parent_topic"],
                child_topic=row["child_topic"],
                expert_difficulty=row["expert_difficulty"],
                expert_score_band=score_band, # Cột quan trọng
            )
            db.add(question)
            count += 1
        
        db.commit()
        print(f"Successfully loaded {count} new questions from CSV.")
        if skipped > 0:
            print(f"Skipped {skipped} duplicates.")

    except FileNotFoundError:
        print(f"ERROR: File {file_path} not found. Make sure you ran the scraper.")
    except Exception as e:
        print(f"ERROR during bulk data load: {e}")
        db.rollback()

if __name__ == '__main__':
    SCRAPED_FILE_PATH = "sat_scraped_data_selenium_final.csv"
    
    # 1. Reset & Re-create Tables
    reset_database()
    
    db = SessionLocal()
    
    # 2. Nạp dữ liệu mẫu (Seed Data)
    load_initial_data(db)
    
    # 3. Nạp dữ liệu thật (Scraped Data)
    load_scraped_data(db, SCRAPED_FILE_PATH)
    
    db.close()
    print("\n=== DATABASE SEEDING COMPLETE ===")
    print("You can now run 'python main.py'")