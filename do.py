import pandas as pd
from bs4 import BeautifulSoup
import re

# 파일 경로 설정
file_path = "D:\\ai_jobs_listUp\\SINGLE_20250826_004620.xlsx"
output_filename = "D:\\ai_jobs_listUp\\ai_jobs_captured_list_2025-08-25.xlsx"
try:
    # 1. 엑셀 파일 읽기
    # HTML 내용이 첫 번째 컬럼(0번 인덱스)에 있다고 가정합니다.
    df = pd.read_excel(file_path, header=None)
    html_snippets = df[0]
    extracted_data = []
    # 2. 각 HTML 스니펫을 파싱하고 정보 추출
    for snippet in html_snippets:
        # 유효한 HTML 문자열인지 확인
        if not isinstance(snippet, str) or not snippet.strip():
            continue
        soup = BeautifulSoup(snippet, "html.parser")
        # 추출된 정보를 저장할 딕셔너리 초기화
        job_info = {
            "회사": "N/A",
            "제목": "N/A",
            "경력": "N/A",
            "근무형태": "N/A",
            "학력": "N/A",
            "근무지역": "N/A",
            "링크": "N/A",
        }
        # 링크 추출
        link_tag = soup.find("a", href=True)
        if link_tag:
            job_info["링크"] = link_tag["href"]
        # 회사명 추출 (section 태그 안의 span)
        company_tag = soup.select_one("section span")
        if company_tag:
            job_info["회사"] = company_tag.get_text(strip=True)
        # 제목 추출 (p 태그 중 ds-web-title2 클래스)
        title_tag = soup.select_one("p.ds-web-title2")
        if title_tag:
            job_info["제목"] = title_tag.get_text(strip=True)
        # 경력, 근무형태, 학력, 근무지역 추출
        # ds-web-summary 클래스를 가진 div 중 두 번째 div가 상세 정보를 포함합니다.
        details_container = soup.select_one("div.ds-web-summary:last-of-type")
        if details_container:
            # 상세 정보 컨테이너의 직접적인 자식 요소들을 찾습니다.
            items = details_container.find_all(recursive=False)
            details = []
            for item in items:
                # span 태그이고, 텍스트가 비어있지 않거나 '·'이 아닌 경우
                if item.name == "span":
                    text = item.get_text(strip=True)
                    if text and text != "·":
                        # 근무지역처럼 div가 중첩된 span인 경우 특별 처리
                        if item.find("div"):
                            nested_span = item.find("span")
                            if nested_span:
                                details.append(nested_span.get_text(strip=True))
                        else:
                            details.append(text)
            # 추출된 순서에 따라 정보 할당
            if len(details) > 0:
                job_info["경력"] = details[0]
            if len(details) > 1:
                job_info["근무형태"] = details[1]
            if len(details) > 2:
                job_info["학력"] = details[2]
            if len(details) > 3:
                job_info["근무지역"] = details[3]
        extracted_data.append(job_info)
    # 3. 새로운 데이터프레임 생성 및 컬럼 순서 재정렬
    if extracted_data:
        processed_df = pd.DataFrame(extracted_data)
        # 요청하신 컬럼 순서로 재정렬
        cols = ["회사", "제목", "경력", "근무형태", "학력", "근무지역", "링크"]
        processed_df = processed_df[cols]
        # 4. 결과 엑셀 파일 저장
        processed_df.to_excel(output_filename, index=False)
        print(
            f"데이터 처리가 완료되었습니다. 결과는 '{output_filename}' 파일에 저장되었습니다."
        )
        print("\n처리된 데이터 샘플:")
        print(processed_df.head().to_string())  # 데이터프레임의 상위 5개 행 출력
    else:
        print(
            "처리할 데이터를 찾지 못했습니다. 원본 엑셀 파일에 유효한 HTML 내용이 없거나 형식이 다를 수 있습니다."
        )
except FileNotFoundError:
    print(f"오류: '{file_path}' 파일을 찾을 수 없습니다. 파일 경로를 확인해 주세요.")
except Exception as e:
    print(f"데이터 처리 중 오류가 발생했습니다: {e}")
