# pip install pandas openpyxl bs4

import pandas as pd
from bs4 import BeautifulSoup
from datetime import date

today = date.today()
formatted_date1 = today.strftime("%Y%m%d")
formatted_date2 = today.strftime("%Y-%m-%d")


file_path = f'sheets/SINGLE_{formatted_date1}.xlsx'
output_filename = f'sheets/ai_jobs_captured_list_{formatted_date2}.xlsx'

df = pd.read_excel(file_path)


htmls = df.iloc[:, 0]
extracted_data = []

def get_job_info(html):
    soup = BeautifulSoup(html, "html.parser")
    job_info = {
        "회사": "N/A",
        "제목": "N/A",
        "경력": "N/A",
        "근무형태": "N/A",
        "학력": "N/A",
        "근무지역": "N/A",
        "링크": "N/A",
    }
    link_tag = soup.find('a', href=True)
    
    if link_tag: # 링크 태그가 존재하는 경우
        job_info["링크"] = link_tag['href']
        
    company_tag = soup.select_one('div section span')
    if company_tag:
        job_info["회사"] = company_tag.get_text(strip=True)
    else:
        company_container = soup.select_one('div.ds-web-summary')
        if company_container:
            company_tag = company_container.find('span')
            if company_tag:
                job_info["회사"] = company_tag.get_text(strip=True)
    
    title_tag = soup.select_one('div div p')
    if title_tag: 
        job_info["제목"] = title_tag.get_text(strip=True)
    
    other_containers = soup.select_one('div.ds-web-summary:last-of-type')
    if other_containers:
        items = other_containers.find_all(recursive=False)
        others = []
        for item in items:
            if item.name == 'span':
                text = item.get_text(strip=True)
                if text and text != "·":
                    others.append(text)
        if len(others) > 0:
            job_info['경력'] = others[0] if len(others) > 0 else "N/A"
            job_info['근무형태'] = others[1] if len(others) > 1 else "N/A"
            job_info['학력'] = others[2] if len(others) > 2 else "N/A"
            job_info['근무지역'] = others[3] if len(others) > 3 else "N/A"

    return job_info

for html in htmls:
    job_info = get_job_info(html)
    extracted_data.append(job_info)

if extracted_data:
    processed_df = pd.DataFrame(extracted_data)
    cols = [
        "회사",
        "제목",
        "경력",
        "근무형태",
        "학력",
        "근무지역",
        "링크"
    ]
    processed_df = processed_df[cols]
    processed_df.to_excel(output_filename, index=False)
    
    print(
        f"데이터 처리가 완료되었습니다. 결과는 '{output_filename}' 파일에 저장되었습니다."
    )
    print(processed_df.head().to_string())  # 데이터프레임의 상위 5개 행 출력