# main.py (UPDATED MAPPING: 1-3 Easy, 4-5 Medium, 6-7 Hard)

import pandas as pd
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
from models import SATExampleCorpus
from llm_classifier import LLMClassifier
from config import GEMINI_MODEL_NAME
import time 
import sys 

def update_models_for_llm_results():
    from sqlalchemy import Column, String, Integer, Text
    if not hasattr(SATExampleCorpus, 'predicted_score'):
        SATExampleCorpus.predicted_score = Column(Integer, nullable=True)
    if not hasattr(SATExampleCorpus, 'llm_reasoning'):
        SATExampleCorpus.llm_reasoning = Column(Text, nullable=True)
    if not hasattr(SATExampleCorpus, 'predicted_difficulty'):
        SATExampleCorpus.predicted_difficulty = Column(String, nullable=True)
    Base.metadata.create_all(bind=engine)

# --- CẬP NHẬT LOGIC MAPPING TẠI ĐÂY ---
def get_difficulty_label(band):
    if band is None: return "N/A"
    
    # 1-3: Easy
    if band <= 3: return "Easy"
    
    # 4-5: Medium
    if band <= 5: return "Medium"
    
    # 6-7: Hard
    return "Hard"

# Trong main.py

def get_few_shot_data(db: Session) -> tuple:
    child_topics = db.query(SATExampleCorpus.child_topic).distinct().all()
    few_shot_data = {}
    
    def find_example(target_band, topic=None):
        query = db.query(SATExampleCorpus).filter(SATExampleCorpus.id > 3)
        if topic: query = query.filter(SATExampleCorpus.child_topic == topic)
        return query.filter(SATExampleCorpus.expert_score_band == target_band).first()

    for topic_tuple in child_topics:
        target_topic = topic_tuple[0]
        examples = []
        
        # --- THAY ĐỔI CHIẾN LƯỢC LẤY MẪU ---
        # Cũ: [2, 4, 6] -> Mới: [1, 4, 7]
        # Mục đích: Show cho AI thấy thế nào là Dễ nhất và Khó nhất
        target_bands = [1, 4, 7] 
        
        for band in target_bands: 
            ex = find_example(band, target_topic)
            # Nếu không có đúng Band 7, cố tìm Band 6
            if not ex: 
                if band == 7: ex = find_example(6, target_topic)
                elif band == 1: ex = find_example(2, target_topic)
                else: ex = find_example(band + 1, target_topic) or find_example(band - 1, target_topic)
            
            if ex: examples.append(ex)
        
        if len(examples) >= 1:
            few_shot_data[target_topic] = LLMClassifier.format_few_shot_prompt(examples)
            
    # Sửa cả fallback prompt
    general_examples = []
    # Lấy đại diện cực trị cho prompt chung
    for band in [1, 4, 7]: 
        ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.expert_score_band == band).first()
        if not ex and band == 7: ex = db.query(SATExampleCorpus).filter(SATExampleCorpus.expert_score_band == 6).first()
        if ex: general_examples.append(ex)
    general_prompt = LLMClassifier.format_few_shot_prompt(general_examples)

    return few_shot_data, general_prompt

def run_assessment(db: Session, classifier: LLMClassifier, few_shot_data: dict, general_prompt: str):
    questions_to_assess = db.query(SATExampleCorpus).filter(
        SATExampleCorpus.id > 3,
        SATExampleCorpus.predicted_score == None 
    ).all()
    
    if not questions_to_assess:
        print("All questions have already been assessed.")
        return

    print(f"Starting Score Band Prediction (1-7) for {len(questions_to_assess)} questions...")
    print("-" * 60)
    
    for i, question in enumerate(questions_to_assess):
        exp_band = question.expert_score_band
        target_label = get_difficulty_label(exp_band)
        
        print(f"\n[{i+1}/{len(questions_to_assess)}] ID: {question.id} | Topic: {question.child_topic}")
        print(f"  Target Band: {exp_band} ({target_label})")
        
        few_shot = few_shot_data.get(question.child_topic, general_prompt)
        q_dict = {
            'child_topic': question.child_topic,
            'question_text': question.question_text,
            'option_a': question.option_a, 'option_b': question.option_b,
            'option_c': question.option_c, 'option_d': question.option_d,
        }
        
        llm_result = classifier.classify_question(q_dict, few_shot)
        
        if 'error' in llm_result:
            print(f"  FAILED: {llm_result['error']}")
        else:
            pred_score = llm_result.get('predicted_score_band', 0)
            reasoning = llm_result.get('reasoning', '')
            
            pred_label = get_difficulty_label(pred_score)
            
            delta_msg = ""
            if exp_band is not None:
                delta = pred_score - exp_band
                icon = "[MATCH]" if delta == 0 else "[DIFF]"
                delta_msg = f"| Delta: {delta:+d} {icon}"

            question.predicted_score = pred_score
            question.predicted_difficulty = f"Band {pred_score} ({pred_label})"
            question.llm_reasoning = reasoning
            
            print(f"  -> AI Prediction: Band {pred_score} ({pred_label}) {delta_msg}")
            
        db.commit()
        sys.stdout.flush()
        time.sleep(4)

if __name__ == '__main__':
    update_models_for_llm_results() 
    try:
        classifier = LLMClassifier(model_name=GEMINI_MODEL_NAME)
    except Exception as e:
        print(f"FATAL: LLM Init failed: {e}")
        exit()
    
    db = SessionLocal()
    try:
        few_shot, gen_prompt = get_few_shot_data(db)
        if few_shot or gen_prompt:
            run_assessment(db, classifier, few_shot, gen_prompt)
        else:
            print("No few-shot data found. Please run seed_data.py.")
    finally:
        db.close()