# api.py (FINAL PRODUCTION: PREDICT + FEEDBACK + CHATBOT + AUTO-SEEDING)

import os
import sys
import traceback
import google.generativeai as genai 
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# --- Internal Imports ---
from database import SessionLocal, engine
import models
from models import SATExampleCorpus
from llm_classifier import LLMClassifier
from config import GEMINI_API_KEY, GEMINI_MODEL_NAME

# --- 0. CONFIGURATION ---
genai.configure(api_key=GEMINI_API_KEY)

# Use 'gemini-2.5-flash' for the Chatbot (Best balance of speed & intelligence)
CHAT_MODEL_NAME = "gemini-2.5-flash" 

CHAT_SYSTEM_PROMPT = """
You are "Zimi", a super cute and energetic AI Teaching Assistant at ZIM Academy. 
Target Audience: English Teachers and Academic Directors.

Your capabilities:
1. Discuss SAT, IELTS, TOEIC teaching methodologies.
2. Explain complex grammar or vocabulary nuances.
3. Suggest lesson plan ideas or classroom activities.

Tone & Style:
- Use lots of emojis (✨, 🤖, 📚, 💖, 🔥, 🚀) to keep the mood light and fun.
- Be encouraging, warm, professional but not stiff.
- Be concise.

Topic Boundaries:
- ONLY discuss: English Teaching, Exam Prep (SAT/IELTS/TOEIC), Pedagogy.
- If asked about something else (e.g., coding, politics), playfully decline: "Opps! Zimi only knows about English & Teaching! 📚 Let's focus on the lesson! ✨"
"""

# --- 1. INITIAL SEED DATA (Dữ liệu mẫu để nạp khi DB rỗng) ---
INITIAL_DATA = [
    {
        "child_topic": "Words in Context",
        "parent_topic": "Craft and Structure",
        "question_text": "The student was ______ to learn that the class had been cancelled, as she had rushed to get there on time.",
        "option_a": "happy", "option_b": "annoyed", "option_c": "indifferent", "option_d": "delighted",
        "expert_score_band": 2, "expert_difficulty": "Easy", "correct_answer": "annoyed"
    },
    {
        "child_topic": "Command of Evidence",
        "parent_topic": "Information and Ideas",
        "question_text": "The researcher claims that the new species of bird nests exclusively in high-altitude pine trees. Which finding, if true, would most directly undermine this claim?",
        "option_a": "The bird is found in pine trees at low altitudes.",
        "option_b": "The bird is found nesting in oak trees at high altitudes.",
        "option_c": "The bird's diet consists mainly of pine nuts.",
        "option_d": "The bird migrates to warmer climates in the winter.",
        "expert_score_band": 4, "expert_difficulty": "Medium", "correct_answer": "The bird is found nesting in oak trees at high altitudes."
    },
    {
        "child_topic": "Transitions",
        "parent_topic": "Expression of Ideas",
        "question_text": "Historically, most economists have regarded the financial sector as a passive intermediary. ______, recent models suggest that financial frictions can significantly amplify business cycle fluctuations.",
        "option_a": "Conversely", "option_b": "Furthermore", "option_c": "Therefore", "option_d": "Specifically",
        "expert_score_band": 6, "expert_difficulty": "Hard", "correct_answer": "Conversely"
    }
]

# --- 2. MAPPINGS & HELPERS ---
CHILD_TO_PARENT_MAP = {
    "Central Ideas and Details": "Information and Ideas",
    "Command of Evidence": "Information and Ideas",
    "Inferences": "Information and Ideas",
    "Words in Context": "Craft and Structure",
    "Text Structure and Purpose": "Craft and Structure",
    "Cross-Text Connections": "Craft and Structure",
    "Rhetorical Synthesis": "Expression of Ideas",
    "Transitions": "Expression of Ideas",
    "Boundaries": "Standard English Conventions",
    "Form, Structure, and Sense": "Standard English Conventions"
}

def get_difficulty_label(band: int) -> str:
    if band <= 3: return "Easy"
    if band <= 5: return "Medium"
    return "Hard"

BACKUP_PROMPT = "Example: The student was [annoyed]..." 
FEW_SHOT_CACHE = {}
CLASSIFIER = None 

# --- 3. DATABASE SEEDING & CACHE LOADING ---
def seed_database(db):
    """Checks if DB is empty and injects initial data."""
    try:
        # Check if any record exists
        if db.query(SATExampleCorpus).first() is None:
            print("🌱 Database is empty. Seeding initial ZIM data...")
            for item in INITIAL_DATA:
                new_ex = SATExampleCorpus(
                    child_topic=item["child_topic"],
                    parent_topic=item["parent_topic"],
                    question_text=item["question_text"],
                    option_a=item["option_a"], option_b=item["option_b"],
                    option_c=item["option_c"], option_d=item["option_d"],
                    expert_score_band=item["expert_score_band"],
                    expert_difficulty=item["expert_difficulty"],
                    correct_answer=item["correct_answer"],
                    expert_notes="Initial Seed"
                )
                db.add(new_ex)
            db.commit()
            print("✅ Seeding complete! AI is ready.")
        else:
            print("👌 Database already has data. Skipping seed.")
    except Exception as e:
        print(f"⚠️ Seeding Error: {e}")

def load_few_shot_data_to_cache():
    global FEW_SHOT_CACHE
    print("🔄 Loading AI Memory...")
    try:
        db = SessionLocal()
        
        # 1. Run Seeding Logic
        seed_database(db)
        
        # 2. Load Data into Cache
        child_topics = db.query(SATExampleCorpus.child_topic).distinct().all()
        for topic_tuple in child_topics:
            target_topic = topic_tuple[0]
            examples = []
            for band in [1, 4, 7]:
                # Try to find exact band match
                ex = db.query(SATExampleCorpus).filter(
                    SATExampleCorpus.child_topic == target_topic,
                    SATExampleCorpus.expert_score_band == band
                ).first()
                # Fallback: Get any example of this topic if exact band missing
                if not ex:
                     ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.child_topic == target_topic).first()
                
                if ex and ex not in examples: examples.append(ex)
            
            if examples:
                FEW_SHOT_CACHE[target_topic] = LLMClassifier.format_few_shot_prompt(examples)
        
        print(f"✅ Cache loaded! Topics: {len(FEW_SHOT_CACHE)}")
        db.close()
    except Exception as e:
        print(f"⚠️ Cache Warning: {e}")
        FEW_SHOT_CACHE["_GENERAL_"] = BACKUP_PROMPT

# --- 4. LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. DB Init
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"DB Warning: {e}")
    
    # 2. AI Init
    try:
        global CLASSIFIER
        CLASSIFIER = LLMClassifier(model_name=GEMINI_MODEL_NAME)
        load_few_shot_data_to_cache()
    except Exception as e:
        print(f"AI Init Error: {e}")
    yield

app = FastAPI(title="SAT AI Predictor + Zimi", version="11.0-Final", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# --- 5. MODELS ---
class QuestionInput(BaseModel):
    child_topic: str; question_text: str; option_a: str; option_b: str; option_c: str; option_d: str

class FeedbackInput(BaseModel):
    child_topic: str; question_text: str; option_a: str; option_b: str; option_c: str; option_d: str; correct_band: int

class PredictionOutput(BaseModel):
    predicted_score_band: int; predicted_label: str; correct_answer: str; reasoning: str; model_used: str

class ChatRequest(BaseModel):
    message: str; history: list = []

# --- 6. ENDPOINTS ---

@app.post("/api/predict", response_model=PredictionOutput)
def predict_sat_difficulty(question: QuestionInput):
    if not CLASSIFIER: raise HTTPException(status_code=500, detail="Server starting...")
    topic_prompt = FEW_SHOT_CACHE.get(question.child_topic, FEW_SHOT_CACHE.get("_GENERAL_", BACKUP_PROMPT))
    try:
        result = CLASSIFIER.classify_question(question.model_dump(), topic_prompt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    if 'error' in result: raise HTTPException(status_code=500, detail=result['error'])
    score = result.get('predicted_score_band', 4)
    return {
        "predicted_score_band": score, "predicted_label": get_difficulty_label(score),
        "correct_answer": result.get('correct_answer', "Unknown"), "reasoning": result.get('reasoning', ""), "model_used": GEMINI_MODEL_NAME
    }

@app.post("/api/feedback")
def submit_feedback(feedback: FeedbackInput):
    print(f"\n📝 FEEDBACK: {feedback.child_topic} -> Band {feedback.correct_band}")
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
        db.commit()
        db.close()
        load_few_shot_data_to_cache() 
        return {"status": "success", "message": "Saved!"}
    except Exception as e:
        print("❌ FEEDBACK ERROR:"); traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")

@app.post("/api/chat")
async def chat_with_zimi(chat: ChatRequest):
    try:
        # Sử dụng gemini-1.5-flash (Model tốt nhất cho Chatbot hiện tại)
        model = genai.GenerativeModel(
            model_name=CHAT_MODEL_NAME, 
            system_instruction=CHAT_SYSTEM_PROMPT
        )
        
        # Chuyển đổi History
        gemini_history = []
        for msg in chat.history:
            role = "user" if msg['role'] == 'user' else "model"
            gemini_history.append({"role": role, "parts": [msg['content']]})

        # Bắt đầu Chat
        chat_session = model.start_chat(history=gemini_history)
        response = chat_session.send_message(chat.message)
        
        return {"reply": response.text}
    except Exception as e:
        print(f"❌ CHAT ERROR: {e}")
        return {"reply": "Opps! Zimi is having a little connection issue 🔌. Could you try asking again? 🥺"}