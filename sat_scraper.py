# sat_scraper.py (ULTIMATE VERSION - Brute Force Button Scan)

import requests
import json
import time
import pandas as pd
from bs4 import BeautifulSoup
import re 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Configuration ---
API_URL_LIST = "https://www.oneprep.xyz/api/questions/list"
API_URL_DETAIL_BASE = "https://www.oneprep.xyz/questions/" 

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

LIST_PARAMS = {
    "program": "sat",
    "difficulty": "E", 
    "limit": 50, 
    "question_set": "sat-suite-question-bank",
    "module": "en",
}

def clean_html_content(html_text):
    if not html_text: return ""
    soup = BeautifulSoup(html_text, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def extract_dialog_value(soup, label_text):
    """Tìm giá trị trong Dialog (đã mở)"""
    # Tìm thẻ p chứa Label (case insensitive)
    label_elem = soup.find('p', string=re.compile(f"^{label_text}$", re.IGNORECASE))
    
    if label_elem and label_elem.parent:
        # Tìm giá trị ở thẻ p kế tiếp hoặc p có class font-medium
        value_elem = label_elem.parent.find('p', class_=re.compile(r'font-medium'))
        if value_elem and value_elem != label_elem:
            return value_elem.get_text(strip=True)
        
        next_p = label_elem.find_next_sibling('p')
        if next_p:
            return next_p.get_text(strip=True)
    return None

# --- Stage 1: Fetch List ---
def fetch_question_list(difficulty_level, num_questions):
    params = LIST_PARAMS.copy()
    params["difficulty"] = difficulty_level
    params["limit"] = num_questions 
    print(f"Fetching list for difficulty: {difficulty_level}...")
    try:
        response = requests.get(API_URL_LIST, headers=HEADERS, params=params) 
        response.raise_for_status()
        raw_data = response.json()
        metadata_list = []
        for q in raw_data.get('questions', []):
            metadata_list.append({
                "id": q["id"],
                "api_difficulty": q.get("difficulty", "UNKNOWN").upper(),
            })
        return metadata_list
    except Exception as e:
        print(f"Error fetching list: {e}")
        return []

# --- Stage 2: Selenium Detail Fetch ---
def fetch_question_details_selenium(driver, question_id, metadata):
    detail_url = f"{API_URL_DETAIL_BASE}{question_id}"
    print(f"  -> Fetching ID {question_id}...", end=" ")
    
    try:
        driver.get(detail_url)
        
        # 1. Wait for content + Hydration
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'question-stimulus'))
        )
        time.sleep(2) # Rất quan trọng: Chờ JS chạy xong (Hydration)
        
        # 2. CLICK INFO BUTTON (Brute Force Strategy)
        # Mã SVG đặc trưng của icon 'info' (lấy đoạn ngắn độc nhất)
        # Full path: M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z
        unique_path_part = "M13 16h-1v-4h-1" 
        
        dialog_opened = False
        
        # Lấy tất cả các thẻ button trên trang
        buttons = driver.find_elements(By.TAG_NAME, "button")
        
        for btn in buttons:
            try:
                # Lấy HTML bên trong button để kiểm tra icon
                inner_html = btn.get_attribute('innerHTML')
                
                # Nếu button chứa đoạn mã SVG path của icon Info
                if unique_path_part in inner_html:
                    # Dùng Javascript để click (tránh bị che bởi element khác)
                    driver.execute_script("arguments[0].click();", btn)
                    
                    # Chờ dialog xuất hiện
                    WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="dialog"]'))
                    )
                    dialog_opened = True
                    # print("Dialog opened!", end=" ")
                    break
            except Exception:
                continue # Bỏ qua lỗi với button này, thử button tiếp theo
        
        if not dialog_opened:
            print("[Warning: Info Dialog NOT opened]", end=" ")

        # 3. Get HTML & Extract
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # --- Extract Metadata ---
        dialog_elem = soup.find('div', role='dialog')
        # Nếu không tìm thấy dialog riêng biệt, tìm trong toàn bộ trang (phòng khi role="dialog" chưa render kịp)
        search_scope = dialog_elem if dialog_elem else soup
        
        parsed_score_band = extract_dialog_value(search_scope, "Score Band")
        parsed_bank_id = extract_dialog_value(search_scope, "Question Bank ID")
        parsed_difficulty = extract_dialog_value(search_scope, "Difficulty")
        parsed_domain = extract_dialog_value(search_scope, "Domain")
        parsed_skill = extract_dialog_value(search_scope, "Skill")
        parsed_section = extract_dialog_value(search_scope, "Section")

        if parsed_score_band:
            print(f"Score Band: {parsed_score_band}", end=" ")
        else:
            print("Score Band: None", end=" ")

        # --- Extract Question Content ---
        stimulus_elem = soup.find('div', class_='question-stimulus')
        stem_elem = soup.find('div', class_='question-stem')
        
        question_text = ""
        if stimulus_elem: question_text += clean_html_content(str(stimulus_elem))
        if stem_elem: question_text += " " + clean_html_content(str(stem_elem))
        
        options = {}
        correct_answer_letter = ""
        option_list_elem = soup.find('div', class_='question-answer-choices')
        if option_list_elem:
            option_elements = option_list_elem.find_all('div', class_='flex items-center gap-3', recursive=False)
            for i, opt_elem in enumerate(option_elements):
                letter = chr(65 + i)
                text_elem = opt_elem.find('div', class_='font-serif text-left')
                options[f"option_{letter.lower()}"] = clean_html_content(str(text_elem)) if text_elem else ""
                
                button_elem = opt_elem.find('div', role='button')
                if button_elem:
                     if 'bg-score-good-background' in button_elem.get('class', []) or button_elem.find(class_='bg-score-good-background'):
                        correct_answer_letter = letter

        print("") # Xuống dòng
        
        result = {
            "question_id": question_id,
            "question_bank_id": parsed_bank_id,
            "section": parsed_section,
            "expert_difficulty": parsed_difficulty if parsed_difficulty else metadata["api_difficulty"],
            "expert_score_band": parsed_score_band,
            "parent_topic": parsed_domain,
            "child_topic": parsed_skill,
            "question_text": question_text,
            "correct_answer": correct_answer_letter,
            **options
        }
        return result

    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == '__main__':
    try:
        service = ChromeService(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') # Uncomment để chạy ẩn, nhưng nên để hiện để debug
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--window-size=1200,800")
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        print(f"FATAL: {e}")
        exit()
        
    all_metadata = []
    # Lấy 50 câu mỗi loại E, M, H
    for diff in ["E", "M", "H"]:
        all_metadata.extend(fetch_question_list(diff, num_questions=50)) 
    
    final_questions = []
    if all_metadata:
        print(f"Total questions to process: {len(all_metadata)}")
        processed_ids = set()
        for meta in all_metadata:
            question_id = meta["id"]
            if question_id not in processed_ids:
                data = fetch_question_details_selenium(driver, question_id, meta)
                if data:
                    final_questions.append(data)
                    processed_ids.add(question_id)

    driver.quit() 
    
    if final_questions:
        df = pd.DataFrame(final_questions)
        
        cols = [
            "question_id", "question_bank_id", 
            "expert_difficulty", "expert_score_band", 
            "section", "parent_topic", "child_topic",
            "question_text", "correct_answer",
            "option_a", "option_b", "option_c", "option_d"
        ]
        
        for col in cols:
            if col not in df.columns: df[col] = ""
        df = df[cols]
        
        df.to_csv("sat_scraped_data_selenium_final.csv", index=False)
        print("\nDone. Data saved to sat_scraped_data_selenium_final.csv")