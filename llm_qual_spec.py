import pandas as pd
import requests
import json
import re
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup, Tag
from datetime import date

today = date.today()
formatted_date = today.strftime("%Y-%m-%d")

# --- 사용자 설정 영역 ---
# 로컬에서 실행 중인 gpt-oss 모델의 API 엔드포인트 주소를 입력하세요.
# (예: Ollama, vLLM 등이 제공하는 OpenAI 호환 엔드포인트)
API_URL = "http://localhost:11434/v1/chat/completions"  # 실제 환경에 맞게 수정하세요.
MODEL_NAME = "gpt-oss"  # 사용 중인 로컬 모델의 이름을 입력하세요.
# -----------------------


def extract_main_content(html_source):
    """
    BeautifulSoup을 사용하여 HTML의 header와 footer 사이의 내용만 추출합니다.
    """
    original_soup = BeautifulSoup(html_source, "html.parser")

    header = original_soup.find("header")
    footer = original_soup.find("footer")

    # header와 footer 사이의 컨텐츠만 담을 리스트
    content_tags = []

    if header:
        for element in header.next_siblings:
            if element is footer:
                break
            # Tag 객체인 경우에만 추가 (NavigableString 같은 다른 타입 제외)
            if isinstance(element, Tag):
                content_tags.append(element)
    else:
        # header가 없으면 body 전체를 대상으로 하되, footer는 제거
        body_content = original_soup.find_all("body")
        if body_content:
            for element in body_content:
                if element is not footer:
                    content_tags.append(element)

    # 추출된 내용으로 새로운 soup 객체를 만들어 순수한 텍스트만 반환
    new_soup = BeautifulSoup("<body></body>", "html.parser")
    body = new_soup.body
    for tag in content_tags:
        body.append(tag)

    # 최종적으로 정제된 텍스트 반환
    return new_soup.get_text(separator=" ", strip=True)


def call_local_llm(html_content):
    """
    로컬 LLM에 정제된 텍스트를 보내 자격요건과 우대사항을 추출합니다.
    """
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
        print(f"  -> LLM 전체 응답: {json.dumps(response_json, indent=2, ensure_ascii=False)}") # 디버깅을 위해 추가
        content_str = response_json["choices"][0]["message"]["content"]

        # JSON 블록을 추출하기 위한 정규 표현식
        # ```json ... ``` 또는 단순히 {...} 형태를 찾습니다.
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", content_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # ```json ... ``` 형태가 아니면 전체 내용을 JSON으로 시도
            json_str = content_str.strip()

        parsed_content = json.loads(json_str)
        return parsed_content
    except requests.exceptions.RequestException as e:
        print(f"  -> LLM API 호출 오류: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  -> LLM 응답 파싱 오류: {e}")
        print(f"  -> 받은 내용: {content_str[:300]}")  # 받은 내용 일부 출력
        return None


def main():
    
    today = date.today()
    formatted_date = today.strftime("%Y-%m-%d")
    
    # 1. 엑셀 파일 읽기
    input_filename = f'sheets/list_with_applyLink_{formatted_date}.xlsx'
    
    try:
        df = pd.read_excel(input_filename)
    except FileNotFoundError:
        print(f"'{input_filename}' 파일을 찾을 수 없습니다.")
        return

    # 2. 셀레니움 웹 드라이버 설정
    driver = webdriver.Chrome()
    results = []

    fail_count = 0

    # 3. 각 링크를 순회하며 정보 추출
    for index, row in df.iterrows():

        if fail_count > 0:
            break

        apply_link = row["지원 링크"]
        print(f"처리 중 ({index + 1}/{len(df)}): {apply_link}")

        job_data = {
            "지원 링크": apply_link,  # 실제 링크 변수 사용
            "자격요건": "추출 실패",
            "우대사항": "추출 실패",
        }

        try:
            driver.get(apply_link)
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState === 'complete'")
            )

            apply_page_html = driver.page_source

            # 메인 컨텐츠만 추출
            main_text = extract_main_content(apply_page_html)

            if not main_text.strip():
                print("  -> 처리할 텍스트 내용이 없습니다.")
                results.append(job_data)
                continue

            # LLM을 호출하여 정보 추출
            print("  -> LLM 호출하여 정보 추출 중...")
            extracted_info = call_local_llm(main_text)

            if extracted_info:
                # LLM의 응답을 직접 출력하여 확인
                print("  --- LLM 원본 응답 ---")
                print(json.dumps(extracted_info, indent=2, ensure_ascii=False))
                print("  --------------------")

                job_data["자격요건"] = "\n".join(extracted_info.get("자격요건", []))
                job_data["우대사항"] = "\n".join(extracted_info.get("우대사항", []))
                print("  -> 정보 추출 완료.")
            else:
                print("  -> 정보 추출 실패.")
                fail_count += 1

        except Exception as e:
            print(f"  -> 처리 중 오류 발생: {type(e).__name__} - {e}")
            # 오류 발생 시 다음 루프로 넘어감

        results.append(job_data)

    driver.quit()

    # 4. 결과 저장
    if results:
        result_df = pd.DataFrame(results)
        # "지원 링크"를 기준으로 원본과 결과 병합
        final_df = pd.merge(df, result_df, on="지원 링크", how="left")

        output_filename = f'sheets/ai_jobs_final_results_{formatted_date}.xlsx'
        final_df.to_excel(output_filename, index=False)
        print(f"\n작업 완료! 결과가 '{output_filename}' 파일에 저장되었습니다.")
    else:
        print("\n처리된 결과가 없어 파일을 저장하지 않았습니다.")


if __name__ == "__main__":
    main()
