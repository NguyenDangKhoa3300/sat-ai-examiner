# llm_classifier.py (FINAL VERSION - SOLVER MODE)

import google.generativeai as genai
import json
import re
from config import GEMINI_API_KEY, GENERATION_CONFIG

class LLMClassifier:
    def __init__(self, model_name):
        if not GEMINI_API_KEY:
             raise ValueError("GEMINI_API_KEY is missing.")
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=GENERATION_CONFIG
        )

    @staticmethod
    def format_few_shot_prompt(examples):
        prompt_text = ""
        for ex in examples:
            band = ex.expert_score_band if ex.expert_score_band else "N/A"
            prompt_text += f"""
--- EXAMPLE (Score Band: {band}) ---
Topic: {ex.child_topic}
Question: {ex.question_text}
Options:
 A: {ex.option_a}
 B: {ex.option_b}
 C: {ex.option_c}
 D: {ex.option_d}
Expert Score: {band}/7
"""
        return prompt_text

    def classify_question(self, question_data, few_shot_prompt):
        system_instruction = """
You are an expert SAT psychometrician. Your task is to:
1. **SOLVE** the question to find the correct answer.
2. **PREDICT** the Score Band (1-7).

**SCORING RUBRIC:**
* **Band 1-2 (Easy):** Explicit answer, simple grammar.
* **Band 3-5 (Medium):** Standard logic, plausible distractors.
* **Band 6-7 (Hard):** Abstract logic, unstated assumptions, tricky distractors.

**TIE-BREAKER RULE:**
If unsure between Band 5 and 6, CHOOSE BAND 6.

**OUTPUT FORMAT (JSON):**
{
  "correct_answer": "Option A/B/C/D",
  "reasoning": "First, state the correct answer clearly. Then explain why based on the text evidence and why other options are wrong. Finally, explain the difficulty level.",
  "predicted_score_band": <integer 1-7>
}
"""
        user_prompt = f"""
{system_instruction}

**REFERENCE EXAMPLES:**
{few_shot_prompt}

**TARGET QUESTION:**
Topic: {question_data['child_topic']}
Question: {question_data['question_text']}
Options:
 A: {question_data['option_a']}
 B: {question_data['option_b']}
 C: {question_data['option_c']}
 D: {question_data['option_d']}

Solve and Predict.
"""
        try:
            response = self.model.generate_content(user_prompt)
            return self._parse_response(response.text)
        except Exception as e:
            return {'error': str(e), 'predicted_score_band': 0}

    def _parse_response(self, text):
        try:
            cleaned_text = re.sub(r"```json|```", "", text).strip()
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # Fallback nếu lỗi JSON
            match = re.search(r'\b([1-7])\b', text)
            score = int(match.group(1)) if match else 4
            return {
                "predicted_score_band": score,
                "correct_answer": "Unknown",
                "reasoning": "JSON Parsing failed. " + text[:100]
            }