# api.py (FINAL PRO VERSION: AUTO-SEEDING DATABASE)

import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Import Modules
from database import SessionLocal, engine
import models
from models import SATExampleCorpus
from llm_classifier import LLMClassifier
from config import GEMINI_MODEL_NAME

# --- DỮ LIỆU MẪU ĐỂ NẠP VÀO DB (SEED DATA) ---
INITIAL_DATA = [
    {
        "child_topic": "Words in Context",
        "question_text": "The student was ______ to learn that the class had been cancelled, as she had rushed to get there on time.",
        "option_a": "happy", "option_b": "annoyed", "option_c": "indifferent", "option_d": "delighted",
        "expert_score_band": 2
    },
    {
        "child_topic": "Command of Evidence",
        "question_text": "The researcher claims that the new species of bird nests exclusively in high-altitude pine trees. Which finding, if true, would most directly undermine this claim?",
        "option_a": "The bird is found in pine trees at low altitudes.",
        "option_b": "The bird is found nesting in oak trees at high altitudes.",
        "option_c": "The bird's diet consists mainly of pine nuts.",
        "option_d": "The bird migrates to warmer climates in the winter.",
        "expert_score_band": 4
    },
    {
        "child_topic": "Inferences",
        "question_text": "While traditional historiography often portrays the industrial revolution as a sudden rupture, recent economic data suggests a more gradual acceleration of productivity. This implies that the term 'revolution' might be a misnomer, reflecting a narrative preference for dramatic change rather than ______ reality.",
        "option_a": "an empirical", "option_b": "a theoretical", "option_c": "a stylistic", "option_d": "a chronological",
        "expert_score_band": 7
    },
     {
        "child_topic": "Boundaries",
        "question_text": "Geneticist Barbara McClintock's discovery of transposons, or 'jumping genes,' fundamentally changed our understanding of genetics______ her work was initially met with skepticism by the scientific community.",
        "option_a": "genetics; however,", "option_b": "genetics, however", "option_c": "genetics however", "option_d": "genetics, however,",
        "expert_score_band": 5
    }
]

# --- CACHE ---
FEW_SHOT_CACHE = {}
CLASSIFIER = None 

def get_difficulty_label(band: int) -> str:
    if band <= 3: return "Easy"
    if band <= 5: return "Medium"
    return "Hard"

def seed_database(db):
    """Hàm nạp dữ liệu nếu DB rỗng"""
    count = db.query(SATExampleCorpus).count()
    if count == 0:
        print("🌱 Database is empty. Seeding initial data...")
        for item in INITIAL_DATA:
            db_item = SATExampleCorpus(**item)
            db.add(db_item)
        db.commit()
        print("✅ Seeding complete!")
    else:
        print(f"👌 Database already has {count} records.")

def load_few_shot_data_to_cache():
    global FEW_SHOT_CACHE
    db = SessionLocal()
    try:
        # Tự động nạp dữ liệu nếu chưa có
        seed_database(db)
        
        # Load dữ liệu vào RAM
        child_topics = db.query(SATExampleCorpus.child_topic).distinct().all()
        
        def find_example(target_band, topic=None):
            query = db.query(SATExampleCorpus)
            if topic: query = query.filter(SATExampleCorpus.child_topic == topic)
            return query.filter(SATExampleCorpus.expert_score_band == target_band).first()

        for topic_tuple in child_topics:
            target_topic = topic_tuple[0]
            examples = []
            for band in [1, 4, 7]:
                ex = find_example(band, target_topic)
                if not ex: 
                    # Logic tìm lân cận
                    if band == 7: ex = find_example(6, target_topic) or find_example(5, target_topic)
                    elif band == 1: ex = find_example(2, target_topic) or find_example(3, target_topic)
                    else: ex = find_example(band+1, target_topic) or find_example(band-1, target_topic)
                if ex: examples.append(ex)
            
            if examples:
                FEW_SHOT_CACHE[target_topic] = LLMClassifier.format_few_shot_prompt(examples)
        
        # Load General
        general_examples = db.query(SATExampleCorpus).limit(3).all()
        if general_examples:
             FEW_SHOT_CACHE["_GENERAL_"] = LLMClassifier.format_few_shot_prompt(general_examples)

        print(f"✅ Cache loaded! Topics: {len(FEW_SHOT_CACHE)}")
        
    except Exception as e:
        print(f"❌ Error DB: {e}")
    finally:
        db.close()

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Tạo bảng trong DB (Nếu chưa có)
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning creating tables: {e}")

    # 2. Khởi tạo AI & Cache
    try:
        global CLASSIFIER
        CLASSIFIER = LLMClassifier(model_name=GEMINI_MODEL_NAME)
        load_few_shot_data_to_cache()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    yield

app = FastAPI(title="SAT AI Predictor", version="3.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

class QuestionInput(BaseModel):
    child_topic: str       
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str

class PredictionOutput(BaseModel):
    predicted_score_band: int 
    predicted_label: str      
    correct_answer: str       
    reasoning: str
    model_used: str

@app.post("/api/predict", response_model=PredictionOutput)
def predict_sat_difficulty(question: QuestionInput):
    if not CLASSIFIER: raise HTTPException(status_code=500, detail="Server starting...")
    
    topic_prompt = FEW_SHOT_CACHE.get(question.child_topic, FEW_SHOT_CACHE.get("_GENERAL_"))
    
    # Fallback nhẹ nếu DB chưa kịp load
    if not topic_prompt: 
        topic_prompt = "Example: Score 4. Question: ... (Data loading)"

    q_dict = question.model_dump()
    try:
        result = CLASSIFIER.classify_question(q_dict, topic_prompt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI Error: {str(e)}")

    if 'error' in result: raise HTTPException(status_code=500, detail=result['error'])

    score = result.get('predicted_score_band', 4)
    
    return {
        "predicted_score_band": score,
        "predicted_label": get_difficulty_label(score),
        "correct_answer": result.get('correct_answer', "Unknown"),
        "reasoning": result.get('reasoning', "No reasoning provided."),
        "model_used": GEMINI_MODEL_NAME
    }