# api.py (LOCAL DEV VERSION)

import os
import sys
import pandas as pd
import io
import traceback
import google.generativeai as genai 
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from sqlalchemy import desc, func

# --- Internal Imports ---
from database import SessionLocal, engine
import models
from models import SATExampleCorpus
from llm_classifier import LLMClassifier
from config import GEMINI_API_KEY, GEMINI_MODEL_NAME

# --- 0. CONFIGURATION ---
genai.configure(api_key=GEMINI_API_KEY)

# Bạn nói bản 2.5 chạy được ở máy bạn, nên tôi để nguyên nhé
CHAT_MODEL_NAME = "gemini-2.5-flash" 

CHAT_SYSTEM_PROMPT = """
You are "Zimi", a super cute and energetic AI Teaching Assistant at ZIM Academy. 
Target Audience: English Teachers and Academic Directors.

Your capabilities:
1. Discuss SAT, IELTS, TOEIC teaching methodologies.
2. Explain complex grammar or vocabulary nuances.
3. Suggest lesson plan ideas.

Tone & Style:
- Use lots of emojis (✨, 🤖, 📚, 💖, 🔥) to keep the mood light.
- Be encouraging, warm, professional but not stiff.
- Be concise.
"""

# --- 1. INITIAL SEED DATA ---
INITIAL_DATA = [
    {
        "child_topic": "Words in Context", "parent_topic": "Craft and Structure",
        "question_text": "The student was ______ to learn that the class had been cancelled...",
        "option_a": "happy", "option_b": "annoyed", "option_c": "indifferent", "option_d": "delighted",
        "expert_score_band": 2, "expert_difficulty": "Easy", "correct_answer": "annoyed"
    },
    {
        "child_topic": "Command of Evidence", "parent_topic": "Information and Ideas",
        "question_text": "The researcher claims that the new species of bird nests exclusively...",
        "option_a": "The bird is found in pine trees...", "option_b": "The bird is found nesting in oak trees...",
        "option_c": "The bird's diet...", "option_d": "The bird migrates...",
        "expert_score_band": 4, "expert_difficulty": "Medium", "correct_answer": "The bird is found nesting in oak trees..."
    },
    {
        "child_topic": "Transitions", "parent_topic": "Expression of Ideas",
        "question_text": "Historically, most economists have regarded the financial sector as...",
        "option_a": "Conversely", "option_b": "Furthermore", "option_c": "Therefore", "option_d": "Specifically",
        "expert_score_band": 6, "expert_difficulty": "Hard", "correct_answer": "Conversely"
    }
]

# --- 2. MAPPINGS & HELPERS ---
CHILD_TO_PARENT_MAP = {
    "Central Ideas and Details": "Information and Ideas", "Command of Evidence": "Information and Ideas",
    "Inferences": "Information and Ideas", "Words in Context": "Craft and Structure",
    "Text Structure and Purpose": "Craft and Structure", "Cross-Text Connections": "Craft and Structure",
    "Rhetorical Synthesis": "Expression of Ideas", "Transitions": "Expression of Ideas",
    "Boundaries": "Standard English Conventions", "Form, Structure, and Sense": "Standard English Conventions"
}

def get_difficulty_label(band: int) -> str:
    if band <= 3: return "Easy"
    if band <= 5: return "Medium"
    return "Hard"

BACKUP_PROMPT = "Example: The student was [annoyed]..." 
FEW_SHOT_CACHE = {}
CLASSIFIER = None 

# --- 3. DATABASE SEEDING & CACHE ---
def seed_database(db):
    try:
        if db.query(SATExampleCorpus).first() is None:
            print("🌱 Database is empty. Seeding initial ZIM data...")
            for item in INITIAL_DATA:
                new_ex = SATExampleCorpus(
                    child_topic=item["child_topic"], parent_topic=item["parent_topic"],
                    question_text=item["question_text"], option_a=item["option_a"], 
                    option_b=item["option_b"], option_c=item["option_c"], option_d=item["option_d"],
                    expert_score_band=item["expert_score_band"], expert_difficulty=item["expert_difficulty"],
                    correct_answer=item["correct_answer"], expert_notes="Initial Seed"
                )
                db.add(new_ex)
            db.commit()
            print("✅ Seeding complete!")
    except Exception as e: print(f"⚠️ Seeding Error: {e}")

def load_few_shot_data_to_cache():
    global FEW_SHOT_CACHE
    print("🔄 Loading AI Memory...")
    try:
        db = SessionLocal()
        seed_database(db)
        child_topics = db.query(SATExampleCorpus.child_topic).distinct().all()
        for topic_tuple in child_topics:
            target_topic = topic_tuple[0]
            examples = []
            for band in [1, 4, 7]:
                ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.child_topic == target_topic, SATExampleCorpus.expert_score_band == band).first()
                if not ex: ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.child_topic == target_topic).first()
                if ex and ex not in examples: examples.append(ex)
            if examples: FEW_SHOT_CACHE[target_topic] = LLMClassifier.format_few_shot_prompt(examples)
        print(f"✅ Cache loaded! Topics: {len(FEW_SHOT_CACHE)}")
        db.close()
    except Exception as e:
        print(f"⚠️ Cache Warning: {e}"); FEW_SHOT_CACHE["_GENERAL_"] = BACKUP_PROMPT

# --- 4. LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    try: models.Base.metadata.create_all(bind=engine)
    except Exception as e: print(f"DB Warning: {e}")
    try:
        global CLASSIFIER
        CLASSIFIER = LLMClassifier(model_name=GEMINI_MODEL_NAME)
        load_few_shot_data_to_cache()
    except Exception as e: print(f"AI Init Error: {e}")
    yield

app = FastAPI(title="SAT AI Predictor + Zimi", version="12.0-Library", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- ROUTING ---
@app.get("/")
async def view_login(): return FileResponse('static/index.html')

@app.get("/app")
async def view_workspace(): return FileResponse('static/workspace.html')

@app.get("/library")
async def view_library(): return FileResponse('static/library.html')

# --- 5. ENDPOINTS ---
class QuestionInput(BaseModel):
    child_topic: str; question_text: str; option_a: str; option_b: str; option_c: str; option_d: str

class FeedbackInput(BaseModel):
    child_topic: str; question_text: str; option_a: str; option_b: str; option_c: str; option_d: str; correct_band: int

class ChatRequest(BaseModel):
    message: str; history: list = []

@app.post("/api/predict")
def predict_sat_difficulty(question: QuestionInput):
    if not CLASSIFIER: raise HTTPException(status_code=500, detail="Server starting...")
    topic_prompt = FEW_SHOT_CACHE.get(question.child_topic, FEW_SHOT_CACHE.get("_GENERAL_", BACKUP_PROMPT))
    try: result = CLASSIFIER.classify_question(question.model_dump(), topic_prompt)
    except Exception as e: raise HTTPException(status_code=503, detail=str(e))
    if 'error' in result: raise HTTPException(status_code=500, detail=result['error'])
    score = result.get('predicted_score_band', 4)
    return {
        "predicted_score_band": score, "predicted_label": get_difficulty_label(score),
        "correct_answer": result.get('correct_answer', "Unknown"), "reasoning": result.get('reasoning', ""), "model_used": GEMINI_MODEL_NAME
    }

@app.post("/api/feedback")
def submit_feedback(feedback: FeedbackInput):
    print(f"📝 FEEDBACK: {feedback.child_topic} -> Band {feedback.correct_band}")
    parent = CHILD_TO_PARENT_MAP.get(feedback.child_topic, "Expression of Ideas") 
    diff_str = get_difficulty_label(feedback.correct_band)
    try:
        db = SessionLocal()
        new_ex = SATExampleCorpus(
            child_topic=feedback.child_topic, parent_topic=parent, expert_difficulty=diff_str,
            question_text=feedback.question_text, option_a=feedback.option_a, 
            option_b=feedback.option_b, option_c=feedback.option_c, option_d=feedback.option_d,
            expert_score_band=feedback.correct_band, correct_answer="Unknown", expert_notes="User Feedback"
        )
        db.add(new_ex)
        db.commit(); db.close()
        load_few_shot_data_to_cache() 
        return {"status": "success", "message": "Saved!"}
    except Exception as e:
        print("❌ FEEDBACK ERROR:"); traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")

@app.post("/api/chat")
async def chat_with_zimi(chat: ChatRequest):
    try:
        model = genai.GenerativeModel(model_name=CHAT_MODEL_NAME, system_instruction=CHAT_SYSTEM_PROMPT)
        gemini_history = [{"role": ("user" if msg['role'] == 'user' else "model"), "parts": [msg['content']]} for msg in chat.history]
        response = model.start_chat(history=gemini_history).send_message(chat.message)
        return {"reply": response.text}
    except Exception as e:
        return {"reply": "Opps! Zimi connection issue 🔌."}

@app.get("/api/questions")
def get_all_questions():
    """Lấy danh sách câu hỏi để hiển thị ở Library"""
    try:
        db = SessionLocal()
        # Lấy 100 câu mới nhất, sắp xếp theo ID giảm dần (mới nhất lên đầu)
        questions = db.query(SATExampleCorpus).order_by(desc(SATExampleCorpus.id)).all()
        db.close()
        return questions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/api/questions/{question_id}")
def delete_question(question_id: int):
    try:
        db = SessionLocal()
        # Tìm câu hỏi theo ID
        question = db.query(SATExampleCorpus).filter(SATExampleCorpus.id == question_id).first()
        
        if not question:
            db.close()
            raise HTTPException(status_code=404, detail="Question not found")
            
        # Xóa và lưu thay đổi
        db.delete(question)
        db.commit()
        db.close()
        
        # Cập nhật lại bộ nhớ đệm cho AI học lại
        load_few_shot_data_to_cache()
        
        return {"status": "success", "message": f"Deleted question #{question_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# --- [NEW] ANALYTICS ROUTE & API ---
@app.get("/analytics")
async def view_analytics():
    return FileResponse('static/analytics.html')

@app.get("/api/analytics-data")
def get_analytics_data():
    try:
        db = SessionLocal()
        
        # 1. Tổng số câu hỏi
        total_questions = db.query(SATExampleCorpus).count()
        
        # 2. Thống kê theo Độ khó (Easy/Medium/Hard)
        diff_query = db.query(SATExampleCorpus.expert_difficulty, func.count(SATExampleCorpus.id)).group_by(SATExampleCorpus.expert_difficulty).all()
        diff_data = {diff: count for diff, count in diff_query}
        
        # 3. Thống kê theo Topic (Top 5 Topic nhiều nhất)
        topic_query = db.query(SATExampleCorpus.child_topic, func.count(SATExampleCorpus.id))\
                        .group_by(SATExampleCorpus.child_topic)\
                        .order_by(func.count(SATExampleCorpus.id).desc())\
                        .limit(8).all()
        topic_labels = [t[0] for t in topic_query]
        topic_values = [t[1] for t in topic_query]

        # 4. Thống kê theo Band điểm (1-7)
        band_query = db.query(SATExampleCorpus.expert_score_band, func.count(SATExampleCorpus.id)).group_by(SATExampleCorpus.expert_score_band).all()
        band_data = {band: count for band, count in band_query}
        
        # Chuẩn hóa dữ liệu Band (đảm bảo có đủ từ 1-7, nếu thiếu thì điền 0)
        final_band_counts = []
        for i in range(1, 8):
            final_band_counts.append(band_data.get(i, 0))

        db.close()
        
        return {
            "total": total_questions,
            "difficulty": {
                "Easy": diff_data.get("Easy", 0),
                "Medium": diff_data.get("Medium", 0),
                "Hard": diff_data.get("Hard", 0)
            },
            "topics": {
                "labels": topic_labels,
                "values": topic_values
            },
            "bands": final_band_counts
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Analytics Error")
    
# --- [UPDATED] BATCH PROCESSING API ---
@app.post("/api/batch-predict")
async def batch_predict_questions(file: UploadFile = File(...)):
    # 1. Kiểm tra AI
    if not CLASSIFIER:
        # Trả về lỗi 503 nếu AI chưa sẵn sàng
        raise HTTPException(status_code=503, detail="AI System chưa khởi động hoặc API Key bị lỗi.")

    try:
        # 2. Đọc file Excel
        contents = await file.read()
        try:
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')
        except Exception:
            raise HTTPException(status_code=400, detail="Không đọc được file Excel. Hãy đảm bảo file không bị hỏng.")

        # Chuẩn hóa tên cột
        df.columns = [str(col).strip() for col in df.columns]
        
        # Kiểm tra cột
        required_columns = ['child_topic', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d']
        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"File thiếu cột: {missing}")

        results = []
        db = SessionLocal()

        # 3. Xử lý từng dòng (Vòng lặp)
        for index, row in df.iterrows():
            # Lấy dữ liệu an toàn
            def get_val(col): return str(row[col]).strip() if pd.notna(row[col]) else ""
            
            q_input = {
                "child_topic": get_val('child_topic'),
                "question_text": get_val('question_text'),
                "option_a": get_val('option_a'), "option_b": get_val('option_b'),
                "option_c": get_val('option_c'), "option_d": get_val('option_d')
            }

            # Nếu không có nội dung câu hỏi, bỏ qua
            if not q_input['question_text']:
                continue

            try:
                # --- GỌI AI ---
                topic_prompt = FEW_SHOT_CACHE.get(q_input["child_topic"], BACKUP_PROMPT)
                ai_result = CLASSIFIER.classify_question(q_input, topic_prompt)

                # Kiểm tra nếu AI trả về lỗi trong dict
                if 'error' in ai_result:
                    raise Exception(ai_result['error'])

                # Thành công
                score = ai_result.get('predicted_score_band', 4)
                label = get_difficulty_label(score)
                reasoning = ai_result.get('reasoning', '')
                ans = ai_result.get('correct_answer', 'Unknown')

                # Lưu DB
                parent = CHILD_TO_PARENT_MAP.get(q_input["child_topic"], "General")
                new_ex = SATExampleCorpus(
                    child_topic=q_input["child_topic"], parent_topic=parent,
                    question_text=q_input["question_text"],
                    option_a=q_input["option_a"], option_b=q_input["option_b"],
                    option_c=q_input["option_c"], option_d=q_input["option_d"],
                    expert_score_band=score, expert_difficulty=label,
                    correct_answer=ans, expert_notes=f"Batch: {reasoning}"
                )
                db.add(new_ex)

                results.append({
                    **q_input,
                    "STATUS": "SUCCESS",
                    "AI Answer": ans,
                    "Band": score,
                    "Reasoning": reasoning
                })

            except Exception as row_e:
                print(f"Row {index} Error: {row_e}")
                # QUAN TRỌNG: Ghi lỗi vào file Excel thay vì bỏ qua
                results.append({
                    **q_input,
                    "STATUS": "ERROR",
                    "AI Answer": "N/A",
                    "Band": 0,
                    "Reasoning": str(row_e)
                })

        db.commit()
        db.close()

        # 4. Xuất file kết quả
        if not results:
            raise HTTPException(status_code=400, detail="File rỗng hoặc không có dữ liệu hợp lệ.")

        output_df = pd.DataFrame(results)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            output_df.to_excel(writer, index=False, sheet_name='AI_Results')
            
            # Tô màu đỏ cho dòng lỗi (Optional visualization logic usually handled here)
            # Ở mức đơn giản, ta chỉ cần xuất dữ liệu ra.

        output.seek(0)
        filename = f"Result_{pd.Timestamp.now().strftime('%H%M%S')}.xlsx"
        
        return StreamingResponse(
            output, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"System Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/download-template")
async def download_excel_template():
    try:
        # Dữ liệu mẫu
        data = [
            {
                "child_topic": "Words in Context",
                "question_text": "The scientist was ______ by the discovery, as it contradicted her previous findings completely.",
                "option_a": "confused",
                "option_b": "vindicated",
                "option_c": "bored",
                "option_d": "unsurprised"
            },
            {
                "child_topic": "Transitions",
                "question_text": "The city has invested heavily in public transport. ______, traffic congestion remains a significant problem.",
                "option_a": "Furthermore",
                "option_b": "However",
                "option_c": "Therefore",
                "option_d": "For example"
            }
        ]
        
        # Tạo DataFrame
        df = pd.DataFrame(data)
        
        # Ghi vào bộ nhớ đệm (RAM)
        output = io.BytesIO()
        # Engine 'openpyxl' bắt buộc phải cài ở Bước 1
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='SAT_Template')
            
            # Chỉnh độ rộng cột cho đẹp
            worksheet = writer.sheets['SAT_Template']
            worksheet.column_dimensions['A'].width = 20
            worksheet.column_dimensions['B'].width = 50
            worksheet.column_dimensions['C'].width = 15
            worksheet.column_dimensions['D'].width = 15
            worksheet.column_dimensions['E'].width = 15
            worksheet.column_dimensions['F'].width = 15

        output.seek(0)
        
        # Trả về file
        return StreamingResponse(
            output, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={"Content-Disposition": "attachment; filename=SAT_Question_Template.xlsx"}
        )
    except Exception as e:
        print(f"Error generating template: {e}") # Xem lỗi trong Terminal nếu có
        raise HTTPException(status_code=500, detail=str(e))