import pandas as pd
import requests
import json
import re
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup, Tag
from datetime import date
import concurrent.futures
import time

# --- 사용자 설정 영역 ---
# 로컬에서 실행 중인 모델들의 정보를 입력하세요.
# (예: Ollama, vLLM 등이 제공하는 OpenAI 호환 엔드포인트)
DEFAULT_MODELS = {
    "gpt-oss:20b": 11434,
    "llama3.1:8b": 11435,
    "solar:latest": 11436,
    # 필요에 따라 모델과 포트를 추가하세요.
}
# -----------------------


def extract_main_content(html_source):
    """
    BeautifulSoup을 사용하여 HTML의 header와 footer 사이의 내용만 추출합니다.
    """
    original_soup = BeautifulSoup(html_source, "html.parser")

    header = original_soup.find("header")
    footer = original_soup.find("footer")

    content_tags = []

    if header:
        for element in header.next_siblings:
            if element is footer:
                break
            if isinstance(element, Tag):
                content_tags.append(element)
    else:
        body_content = original_soup.find_all("body")
        if body_content:
            for element in body_content:
                if element is not footer:
                    content_tags.append(element)

    new_soup = BeautifulSoup("<body></body>", "html.parser")
    body = new_soup.body
    for tag in content_tags:
        body.append(tag)

    return new_soup.get_text(separator=" ", strip=True)


def call_local_llm(html_content, model_name, port):
    """
    로컬 LLM에 정제된 텍스트를 보내 자격요건과 우대사항을 추출합니다.
    """
    api_url = f"http://localhost:{port}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}

    prompt = f"""
    다음은 채용 공고 페이지의 내용입니다. 이 내용에서 '자격요건'과 '우대사항'을 찾아서 각각 정리하라.
    결과는 반드시 아래와 같은 JSON 형식으로만 응답하라. 만약 내용이 없다면 빈 리스트([])로 응답하라.

    {{
      "자격요건": [
        "자격요건1",
        "자격요건2",
        ....
      ],
      "우대사항": [
        "우대사항1",
        "우대사항2",
        ....
      ]
    }}

    --- 공고 내용 시작 ---
    {html_content}
    --- 공고 내용 끝 ---
    """

    data = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }

    try:
        response = requests.post(
            api_url, headers=headers, data=json.dumps(data), timeout=180
        )
        response.raise_for_status()
        response_json = response.json()
        content_str = response_json["choices"][0]["message"]["content"]

        json_match = re.search(r"```json\s*(\{.*\})\s*```", content_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content_str.strip()

        parsed_content = json.loads(json_str)
        return parsed_content
    except requests.exceptions.RequestException as e:
        print(f"  -> [{model_name}] LLM API 호출 오류: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  -> [{model_name}] LLM 응답 파싱 오류: {e}")
        return None


def select_models():
    """
    사용자로부터 여러 모델을 선택받습니다.
    """
    model_list = list(DEFAULT_MODELS.keys())
    print("사용할 모델을 모두 선택하세요 (번호를 쉼표로 구분하여 입력, 예: 1,3):")
    for idx, model in enumerate(model_list, 1):
        print(f"{idx}. {model} (Port: {DEFAULT_MODELS[model]})")
    
    while True:
        try:
            choices = input("번호 입력: ")
            selected_indices = [int(c.strip()) - 1 for c in choices.split(',')]
            if all(0 <= i < len(model_list) for i in selected_indices):
                selected_models = {model_list[i]: DEFAULT_MODELS[model_list[i]] for i in selected_indices}
                if selected_models:
                    return selected_models
                else:
                    print("하나 이상의 모델을 선택해야 합니다.")
            else:
                print("올바른 번호를 입력하세요.")
        except (ValueError, IndexError):
            print("잘못된 입력입니다. 번호를 쉼표로 구분하여 다시 입력하세요.")

def process_link_for_model(args):
    """
    단일 링크와 단일 모델에 대한 정보 추출 작업을 수행합니다. (병렬 처리를 위한 함수)
    """
    index, total, apply_link, html_source, model_name, port = args
    
    print(f"  -> ({index}/{total}) 링크의 '{model_name}' 모델 처리 시작...")
    
    main_text = extract_main_content(html_source)

    if not main_text.strip():
        print(f"  -> [{model_name}] 처리할 텍스트 내용이 없습니다.")
        return {"지원 링크": apply_link, "model": model_name, "자격요건": "내용 없음", "우대사항": "내용 없음"}

    extracted_info = call_local_llm(main_text, model_name, port)

    if extracted_info:
        qualifications = "\n".join(extracted_info.get("자격요건", []))
        preferences = "\n".join(extracted_info.get("우대사항", []))
        print(f"  -> [{model_name}] 정보 추출 완료.")
        return {"지원 링크": apply_link, "model": model_name, "자격요건": qualifications, "우대사항": preferences}
    else:
        print(f"  -> [{model_name}] 정보 추출 실패.")
        return {"지원 링크": apply_link, "model": model_name, "자격요건": "추출 실패", "우대사항": "추출 실패"}

def main():
    start_time = time.time()
    
    selected_models = select_models()
    print(f"\n선택된 모델: {', '.join(selected_models.keys())}\n")

    today = date.today()
    formatted_date = today.strftime("%Y-%m-%d")
    
    input_filename = f'sheets/list_with_applyLink_{formatted_date}.xlsx'
    try:
        df = pd.read_excel(input_filename)
    except FileNotFoundError:
        print(f"'{input_filename}' 파일을 찾을 수 없습니다.")
        return

    # 1. (순차적) 셀레니움을 사용하여 모든 페이지의 HTML 소스 가져오기
    print("--- 1. 모든 채용 공고 페이지의 HTML 소스를 가져오는 중... ---")
    driver = webdriver.Chrome()
    link_to_html = {}
    for index, row in df.iterrows():
        apply_link = row["지원 링크"]
        print(f"페이지 로딩 중 ({index + 1}/{len(df)}): {apply_link}")
        try:
            driver.get(apply_link)
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState === 'complete'")
            )
            link_to_html[apply_link] = driver.page_source
        except Exception as e:
            print(f"  -> 페이지 로딩 오류: {e}")
            link_to_html[apply_link] = "<html><body>오류 발생</body></html>"
    driver.quit()
    print("--- HTML 소스 가져오기 완료 ---")

    # 2. (병렬) 각 링크와 모델에 대해 정보 추출 실행
    print("--- 2. LLM을 호출하여 병렬로 정보 추출 시작... ---")
    tasks = []
    for i, row in df.iterrows():
        apply_link = row["지원 링크"]
        html_source = link_to_html.get(apply_link)
        if html_source:
            for model_name, port in selected_models.items():
                tasks.append(((i + 1), len(df), apply_link, html_source, model_name, port))

    all_results = []
    # 병렬 처리 스레드 수를 모델 수에 맞춰 제한 (API 서버 부하 조절)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected_models)) as executor:
        future_to_task = {executor.submit(process_link_for_model, task): task for task in tasks}
        for future in concurrent.futures.as_completed(future_to_task):
            try:
                result = future.result()
                if result:
                    all_results.append(result)
            except Exception as e:
                print(f"  -> 태스크 실행 중 오류 발생: {e}")

    print("--- 정보 추출 완료---")

    # 3. 결과 취합 및 저장
    print("--- 3. 결과 취합 및 파일 저장 중... ---")
    if all_results:
        result_df = pd.DataFrame(all_results)
        
        # 피벗 테이블을 사용하여 각 모델의 결과를 별도의 열로 만듦
        pivot_df = result_df.pivot(index="지원 링크", columns="model", values=["자격요건", "우대사항"])
        
        # 멀티레벨 컬럼을 단일 레벨로 만듦 (예: ('자격요건', 'gpt-oss:20b') -> '자격요건 (gpt-oss:20b)')
        pivot_df.columns = [f'{val} ({col})' for val, col in pivot_df.columns]
        
        # 원본 데이터프레임과 병합
        final_df = pd.merge(df, pivot_df, on="지원 링크", how="left")

        output_filename = f'sheets/ai_jobs_final_results_{formatted_date}_comparison.xlsx'
        final_df.to_excel(output_filename, index=False)
        print(f"\n작업 완료! 결과가 '{output_filename}' 파일에 저장되었습니다.")
    else:
        print("\n처리된 결과가 없어 파일을 저장하지 않았습니다.")
        
    end_time = time.time()
    print(f"총 소요 시간: {end_time - start_time:.2f}초")


if __name__ == "__main__":
    main()