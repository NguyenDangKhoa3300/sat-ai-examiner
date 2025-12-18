# api.py (ULTIMATE VERSION: PREDICT + FEEDBACK + CUTE CHATBOT)

import os
import sys
import traceback
import google.generativeai as genai # Required for Chatbot
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

# --- 0. CHATBOT CONFIGURATION (NEW) ---
# Configure Gemini directly for the Chat feature
genai.configure(api_key=GEMINI_API_KEY)

# The Persona for the Chatbot
CHAT_SYSTEM_PROMPT = """
You are "Zimi", a cute and expert AI Teaching Assistant at ZIM Academy.
Target Audience: English Teachers and Academic Directors.
Your capabilities:
1. Discuss SAT, IELTS, TOEIC teaching methodologies.
2. Explain complex grammar or vocabulary nuances.
3. Suggest lesson plan ideas.

Tone & Style:
- Professional but very friendly and encouraging.
- Use emojis (✨, 📚, 💡, 🤖) frequently to keep the mood light.
- Be concise and helpful.
- If asked about non-educational topics, playfully guide them back to English teaching.
"""

# --- 1. TOPIC & DIFFICULTY MAPPING ---
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
    """Converts numerical band (1-7) to text label."""
    if band <= 3: return "Easy"
    if band <= 5: return "Medium"
    return "Hard"

# --- CONFIGURATION & CACHE ---
BACKUP_PROMPT = "Example: ..." 
FEW_SHOT_CACHE = {}
CLASSIFIER = None 

def load_few_shot_data_to_cache():
    """Loads example questions from Database into RAM for Few-shot prompting."""
    global FEW_SHOT_CACHE
    print("🔄 Loading AI Memory (Few-shot Cache)...")
    try:
        db = SessionLocal()
        child_topics = db.query(SATExampleCorpus.child_topic).distinct().all()
        
        for topic_tuple in child_topics:
            target_topic = topic_tuple[0]
            examples = []
            for band in [1, 4, 7]:
                ex = db.query(SATExampleCorpus).filter(
                    SATExampleCorpus.child_topic == target_topic,
                    SATExampleCorpus.expert_score_band == band
                ).first()
                if ex: examples.append(ex)
            
            if examples:
                FEW_SHOT_CACHE[target_topic] = LLMClassifier.format_few_shot_prompt(examples)
                
        print(f"✅ Cache loaded successfully! Topics covered: {len(FEW_SHOT_CACHE)}")
        db.close()
    except Exception as e:
        print(f"⚠️ Cache Load Warning (Using Backup): {e}")
        FEW_SHOT_CACHE["_GENERAL_"] = BACKUP_PROMPT

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"DB Warning: {e}")
    
    try:
        global CLASSIFIER
        CLASSIFIER = LLMClassifier(model_name=GEMINI_MODEL_NAME)
        load_few_shot_data_to_cache()
    except Exception as e:
        print(f"AI Init Error: {e}")
    yield

app = FastAPI(title="SAT AI Predictor + Zimi Chat", version="9.0-Chatbot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# --- DATA MODELS ---
class QuestionInput(BaseModel):
    child_topic: str       
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str

class FeedbackInput(BaseModel):
    child_topic: str
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_band: int

class PredictionOutput(BaseModel):
    predicted_score_band: int 
    predicted_label: str      
    correct_answer: str       
    reasoning: str
    model_used: str

# [NEW] Chat Models
class ChatRequest(BaseModel):
    message: str
    history: list = [] # List of previous messages context

# --- ENDPOINTS ---

# 1. PREDICT
@app.post("/api/predict", response_model=PredictionOutput)
def predict_sat_difficulty(question: QuestionInput):
    if not CLASSIFIER: raise HTTPException(status_code=500, detail="Server starting...")
    topic_prompt = FEW_SHOT_CACHE.get(question.child_topic, FEW_SHOT_CACHE.get("_GENERAL_", BACKUP_PROMPT))
    q_dict = question.model_dump()

    try:
        result = CLASSIFIER.classify_question(q_dict, topic_prompt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

    if 'error' in result: raise HTTPException(status_code=500, detail=result['error'])

    score = result.get('predicted_score_band', 4)
    return {
        "predicted_score_band": score,
        "predicted_label": get_difficulty_label(score),
        "correct_answer": result.get('correct_answer', "Unknown"),
        "reasoning": result.get('reasoning', "No reasoning provided."),
        "model_used": GEMINI_MODEL_NAME
    }

# 2. FEEDBACK
@app.post("/api/feedback")
def submit_feedback(feedback: FeedbackInput):
    print(f"\n📝 RECEIVING FEEDBACK: {feedback.child_topic} -> Band {feedback.correct_band}")
    parent = CHILD_TO_PARENT_MAP.get(feedback.child_topic, "Expression of Ideas") 
    difficulty_str = get_difficulty_label(feedback.correct_band)

    try:
        db = SessionLocal()
        new_example = SATExampleCorpus(
            child_topic=feedback.child_topic,
            parent_topic=parent,
            expert_difficulty=difficulty_str,
            question_text=feedback.question_text,
            option_a=feedback.option_a,
            option_b=feedback.option_b,
            option_c=feedback.option_c,
            option_d=feedback.option_d,
            expert_score_band=feedback.correct_band,
            correct_answer="Unknown",          
            expert_notes="User Feedback"
        )
        db.add(new_example)
        db.commit()
        db.close()
        load_few_shot_data_to_cache() 
        return {"status": "success", "message": "Feedback saved!"}
    except Exception as e:
        print("❌ ERROR SAVING FEEDBACK:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")

# 3. [NEW] CHATBOT ENDPOINT
@app.post("/api/chat")
async def chat_with_zimi(chat: ChatRequest):
    try:
        # Create a new model instance for chat
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Prepare history in Gemini format
        formatted_history = []
        # Add System Prompt as the first turn (User says prompt -> Model says OK)
        formatted_history.append({"role": "user", "parts": [CHAT_SYSTEM_PROMPT]})
        formatted_history.append({"role": "model", "parts": ["Understood! I am Zimi, ready to help! ✨"]})
        
        # Append user's conversation history
        for msg in chat.history:
            role = "user" if msg['role'] == 'user' else "model"
            formatted_history.append({"role": role, "parts": [msg['content']]})

        # Start chat session
        chat_session = model.start_chat(history=formatted_history)
        
        # Send new message
        response = chat_session.send_message(chat.message)
        
        return {"reply": response.text}
    except Exception as e:
        print(f"Chat Error: {e}")
        return {"reply": "Opps! Zimi is having a little brain freeze 🧊. Can you say that again? 🥺"}