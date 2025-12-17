# api.py (FINAL PRODUCTION VERSION)

from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Import các module nội bộ
from database import SessionLocal
from models import SATExampleCorpus
from llm_classifier import LLMClassifier
from config import GEMINI_MODEL_NAME

# --- CẤU HÌNH CACHE ---
FEW_SHOT_CACHE = {}
CLASSIFIER = None 

def get_difficulty_label(band: int) -> str:
    if band <= 3: return "Easy"
    if band <= 5: return "Medium"
    return "Hard"

def load_few_shot_data_to_cache():
    db = SessionLocal()
    print("Loading Few-shot examples from Database...")
    try:
        child_topics = db.query(SATExampleCorpus.child_topic).distinct().all()
        
        def find_example(target_band, topic=None):
            query = db.query(SATExampleCorpus).filter(SATExampleCorpus.id > 3)
            if topic: query = query.filter(SATExampleCorpus.child_topic == topic)
            return query.filter(SATExampleCorpus.expert_score_band == target_band).first()

        for topic_tuple in child_topics:
            target_topic = topic_tuple[0]
            examples = []
            for band in [1, 4, 7]:
                ex = find_example(band, target_topic)
                if not ex: 
                    if band == 7: ex = find_example(6, target_topic)
                    elif band == 1: ex = find_example(2, target_topic)
                    else: ex = find_example(band+1, target_topic) or find_example(band-1, target_topic)
                if ex: examples.append(ex)
            if examples:
                FEW_SHOT_CACHE[target_topic] = LLMClassifier.format_few_shot_prompt(examples)

        general_examples = []
        for band in [1, 4, 7]:
            ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.expert_score_band == band).first()
            if not ex and band == 7: ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.expert_score_band == 6).first()
            if ex: general_examples.append(ex)
        FEW_SHOT_CACHE["_GENERAL_"] = LLMClassifier.format_few_shot_prompt(general_examples)
        
        print(f"✅ Cache loaded successfully! Topics covered: {len(FEW_SHOT_CACHE) - 1}")
    except Exception as e:
        print(f"❌ Error loading cache: {e}")
    finally:
        db.close()

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        global CLASSIFIER
        print("Initializing AI Model...")
        CLASSIFIER = LLMClassifier(model_name=GEMINI_MODEL_NAME)
        load_few_shot_data_to_cache()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    yield
    print("Shutting down API...")

# --- APP ---
app = FastAPI(title="SAT AI Predictor", version="2.0", lifespan=lifespan)
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
    correct_answer: str       # <--- MỚI: Đáp án đúng
    reasoning: str
    model_used: str

@app.post("/api/predict", response_model=PredictionOutput)
def predict_sat_difficulty(question: QuestionInput):
    if not CLASSIFIER: raise HTTPException(status_code=500, detail="Server initializing...")
    
    topic_prompt = FEW_SHOT_CACHE.get(question.child_topic, FEW_SHOT_CACHE.get("_GENERAL_"))
    if not topic_prompt: raise HTTPException(status_code=500, detail="Database empty.")

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