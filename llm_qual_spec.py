import pandas as pd
import requests
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from bs4 import BeautifulSoup

# --- 사용자 설정 영역 ---
# 로컬에서 실행 중인 gpt-oss 모델의 API 엔드포인트 주소를 입력하세요.
# (예: Ollama, vLLM 등이 제공하는 OpenAI 호환 엔드포인트)
API_URL = "http://localhost:11434/v1/chat/completions" # 예시 주소입니다. 실제 환경에 맞게 수정하세요.
MODEL_NAME = "gpt-oss" # 사용 중인 로컬 모델의 이름을 입력하세요.

# -----------------------

def call_local_llm(html_content):
    """
    로컬 LLM에 HTML을 보내 자격요건과 우대사항을 추출합니다.
    """
    headers = {
        "Content-Type": "application/json"
    }
    
    # 모델에게 보낼 프롬프트입니다. JSON 형식으로 답변을 유도합니다.
    prompt = f"""
    다음은 채용 공고 페이지의 HTML 내용입니다. 이 내용에서 '자격요건'과 '우대사항'을 찾아서 각각 정리하라.
    결과는 반드시 아래와 같은 JSON 형식으로만 응답해주세요. 만약 내용이 없다면 빈 리스트([])로 응답하라.

    {{
      "자격요건": [
        "자격요건1",
        "자격요건2",
        .....
      ],
      "우대사항": [
        "우대사항1",
        "우대사항2",
        .....
      ]
    }}

    --- HTML 시작 ---
    {html_content}
    --- HTML 끝 ---
    """

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "response_format": {"type": "json_object"} # JSON 출력 강제 (지원하는 모델일 경우)
    }

    try:
        response = requests.post(API_URL, headers=headers, data=json.dumps(data), timeout=300) # 타임아웃 5분
        response.raise_for_status()
        
        # 모델의 응답에서 JSON 부분만 추출
        response_json = response.json()
        content_str = response_json['choices'][0]['message']['content']
        
        # 문자열을 실제 JSON 객체로 파싱
        parsed_content = json.loads(content_str)
        return parsed_content

    except requests.exceptions.RequestException as e:
        print(f"  -> LLM API 호출 오류: {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  -> LLM 응답 파싱 오류: {e}")
        return None


# 1. 엑셀 파일 읽기
input_filename = "ai_jobs_captured_list_2025-08-26.xlsx"
try:
    df = pd.read_excel(input_filename)
except FileNotFoundError:
    print(f"'{input_filename}' 파일을 찾을 수 없습니다. 파일 이름을 확인해주세요.")
    exit()

# 2. 셀레니움 웹 드라이버 설정
driver = webdriver.Chrome()

results = []

# 3. 각 링크를 순회하며 정보 추출
for index, row in df.iterrows():
    original_link = row["링크"]
    print(f"처리 중 ({index + 1}/{len(df)}): {original_link}")
    
    job_data = {
        "링크": original_link,
        "지원 링크": "추출 실패",
        "자격요건": "추출 실패",
        "우대사항": "추출 실패"
    }

    try:
        driver.get(original_link)
        wait = WebDriverWait(driver, 10)
        
        wait.until(lambda driver: driver.execute_script("return document.readyState === 'complete'"))
        apply_button = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'bg-primary') and contains(., '지원하기')]" )))
        
        original_window = driver.current_window_handle
        driver.execute_script("arguments[0].click();", apply_button)
        wait.until(EC.number_of_windows_to_be(2))

        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                break
        
        time.sleep(1)
        
        # 새 탭의 URL과 HTML 소스 가져오기
        apply_page_url = driver.current_url
        apply_page_html = driver.page_source
        job_data["지원 링크"] = apply_page_url
        print(f"  -> 지원 링크: {apply_page_url}")

        # HTML에서 관련 섹션만 추출
        soup = BeautifulSoup(apply_page_html, 'html.parser')

        # '자격요건' 또는 '우대사항' 텍스트를 포함하는 섹션 찾기
        relevant_content = []
        keywords = ["자격", "우대", "requirements", "qualifications", "preferred", "skills", "responsibilities"]

        for keyword in keywords:
            # 텍스트를 포함하는 모든 요소 찾기
            elements_with_keyword = soup.find_all(lambda tag: tag.name in ['div', 'section', 'p', 'li'] and keyword.lower() in tag.get_text().lower()) # 대소문자 구분 없이 검색
            for element in elements_with_keyword:
                # 해당 요소의 부모 섹션 또는 div를 찾아서 추가 (너무 상위로 가지 않도록 제한)
                current_element = element
                found_section = False
                for _ in range(5): # 최대 5단계 부모까지 탐색
                    # 클래스 이름에 'content' 또는 'description'이 포함된 섹션/div를 우선적으로 찾음
                    if current_element.name in ['section', 'div'] and \
                       ('class' in current_element.attrs and \
                        any(cls in ['content', 'description', 'job-details', 'section-body'] for cls in current_element['class'])):
                        relevant_content.append(str(current_element))
                        found_section = True
                        break
                    if current_element.parent:
                        current_element = current_element.parent
                    else:
                        break
                if not found_section: # 특정 섹션을 찾지 못하면 그냥 요소 자체를 추가
                    relevant_content.append(str(element))

        if relevant_content:
            # 중복 제거 및 HTML 결합
            processed_html = "\n".join(list(set(relevant_content)))
            print("  -> HTML 내용 축소 완료.")
        else:
            # 관련 섹션을 찾지 못하면, body 태그의 내용을 제한적으로 사용
            body_content = soup.find('body')
            if body_content:
                # 너무 크지 않도록 처음 10000자 정도만 사용 (대략적인 값, 이전 5000자에서 늘림)
                processed_html = str(body_content.get_text())[:10000] # 텍스트만 추출하여 크기 줄임
                print("  -> HTML 내용 축소 (body 태그 일부) 완료.")
            else:
                processed_html = apply_page_html # 최후의 수단: 전체 HTML 사용
                print("  -> HTML 내용 축소 실패. 전체 HTML 사용.")

        # LLM을 호출하여 정보 추출
        print("  -> LLM 호출하여 정보 추출 중...")
        extracted_info = call_local_llm(processed_html)
        
        if extracted_info:
            # join을 사용하여 리스트를 줄바꿈이 있는 문자열로 변환
            job_data["자격요건"] = "\n".join(extracted_info.get("자격요건", []))
            job_data["우대사항"] = "\n".join(extracted_info.get("우대사항", []))
            print("  -> 정보 추출 완료.")
        else:
            print("  -> 정보 추출 실패.")
            break

        driver.close()
        driver.switch_to.window(original_window)

    except Exception as e:
        print(f"  -> 셀레니움 처리 중 오류 발생: {type(e).__name__} - {e}")
        break
    
    results.append(job_data)


driver.quit()

# 4. 결과 저장
# 원본 데이터와 새로운 데이터를 합치기
result_df = pd.DataFrame(results)
# 원본 df에서 '링크' 열을 기준으로 합치기 위해 인덱스를 맞춥니다.
final_df = df.merge(result_df, on="링크", how="left")


output_filename = "ai_jobs_final_results.xlsx"
final_df.to_excel(output_filename, index=False)

print(f"\n작업 완료! 결과가 '{output_filename}' 파일에 저장되었습니다.")
