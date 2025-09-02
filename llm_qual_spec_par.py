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

today = date.today()
formatted_date = today.strftime("%Y-%m-%d")

# --- 사용자 설정 영역 ---
# 로컬에서 실행 중인 gpt-oss 모델의 API 엔드포인트 주소를 입력하세요.
# (예: Ollama, vLLM 등이 제공하는 OpenAI 호환 엔드포인트)
API_URL = "http://localhost:11434/v1/chat/completions"  # 실제 환경에 맞게 수정하세요.
MODEL_NAME = "gpt-oss"  # 사용 중인 로컬 모델의 이름을 입력하세요.
MAX_WORKERS = 5  # 병렬로 처리할 스레드 수 (컴퓨터 및 로컬 LLM 서버 사양에 맞게 조절)
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


def call_local_llm(text_content):
    """
    로컬 LLM에 정제된 텍스트를 보내 자격요건과 우대사항을 추출합니다.
    """
    if not text_content or not text_content.strip():
        return None

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
    {text_content}
    --- 공고 내용 끝 ---
    """

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }

    try:
        response = requests.post(
            API_URL, headers=headers, data=json.dumps(data), timeout=300
        )
        response.raise_for_status()
        response_json = response.json()
        content_str = response_json["choices"][0]["message"]["content"]

        json_match = re.search(
            r"```json\s*(\{[\s\S]*?\})\s*```", content_str, re.DOTALL
        )
        if json_match:
            json_str = json_match.group(1)
        else:
            start = content_str.find("{")
            end = content_str.rfind("}")
            if start != -1 and end != -1 and start < end:
                json_str = content_str[start : end + 1]
            else:
                json_str = content_str

        parsed_content = json.loads(json_str)
        return parsed_content
    except requests.exceptions.RequestException as e:
        print(f"  -> LLM API 호출 오류: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  -> LLM 응답 파싱 오류: {e}")
        print(f"  -> 받은 내용: {content_str[:300]}")
        return None


def main():
    start_time = time.time()

    today = date.today()
    formatted_date = today.strftime("%Y-%m-%d")

    input_filename = f"sheets/list_with_applyLink_{formatted_date}.xlsx"

    try:
        df = pd.read_excel(input_filename)
    except FileNotFoundError:
        print(f"'{input_filename}' 파일을 찾을 수 없습니다.")
        return

    # 1. 모든 링크에서 HTML 컨텐츠 수집
    print("--- 1. HTML 컨텐츠 수집 시작 ---")
    driver = webdriver.Chrome()
    pages_to_process = []
    for index, row in df.iterrows():
        apply_link = row["지원 링크"]
        print(f"  - 수집 중 ({index + 1}/{len(df)}): {apply_link}")

        page_info = {"지원 링크": apply_link, "text": None}
        try:
            driver.get(apply_link)
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState === 'complete'")
            )
            main_text = extract_main_content(driver.page_source)
            if main_text and main_text.strip():
                page_info["text"] = main_text
            else:
                print("    -> 내용 없음.")
        except Exception as e:
            print(f"    -> 오류 발생: {type(e).__name__} - {e}")
        pages_to_process.append(page_info)
    driver.quit()
    print("--- HTML 컨텐츠 수집 완료 ---")

    # 2. LLM 병렬 호출로 정보 추출
    print(f"--- 2. LLM 병렬 호출 시작 (Worker: {MAX_WORKERS}개) ---")
    results = []

    processable_pages = [p for p in pages_to_process if p["text"]]

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_page = {
            executor.submit(call_local_llm, page["text"]): page
            for page in processable_pages
        }

        total_pages = len(future_to_page)
        print(f"  -> LLM에 정보 추출 요청... (총 {total_pages}개)")

        for i, future in enumerate(concurrent.futures.as_completed(future_to_page)):
            page = future_to_page[future]
            apply_link = page["지원 링크"]
            print(f"  - 처리 완료 ({i + 1}/{total_pages}): {apply_link}")

            job_data = {
                "지원 링크": apply_link,
                "자격요건": "추출 실패",
                "우대사항": "추출 실패",
            }

            try:
                extracted_info = future.result()
                if extracted_info:
                    job_data["자격요건"] = "\n".join(extracted_info.get("자격요건", []))
                    job_data["우대사항"] = "\n".join(extracted_info.get("우대사항", []))
            except Exception as e:
                print(f"    -> 병렬 처리 중 오류: {type(e).__name__} - {e}")

            results.append(job_data)

    # HTML 수집에 실패했거나 내용이 없던 페이지들 처리
    failed_pages = [p for p in pages_to_process if not p["text"]]
    for page in failed_pages:
        results.append(
            {
                "지원 링크": page["지원 링크"],
                "자격요건": "HTML 수집 실패 또는 내용 없음",
                "우대사항": "HTML 수집 실패 또는 내용 없음",
            }
        )

    print("--- LLM 병렬 호출 완료 ---")

    # 3. 결과 저장
    if results:
        print("--- 3. 결과 병합 및 저장 시작 ---")
        result_df = pd.DataFrame(results)
        final_df = pd.merge(df, result_df, on="지원 링크", how="left")

        output_filename = f"sheets/ai_jobs_final_results_{formatted_date}.xlsx"
        final_df.to_excel(output_filename, index=False)
        print(f"  -> 작업 완료! 결과가 '{output_filename}' 파일에 저장되었습니다.")
    else:
        print("처리된 결과가 없어 파일을 저장하지 않았습니다.")

    end_time = time.time()
    print(f"\n총 소요 시간: {end_time - start_time:.2f}초")


if __name__ == "__main__":
    main()
