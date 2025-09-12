import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import date
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def get_job_info(job_item):
    """개별 채용 공고 아이템(BeautifulSoup Tag)에서 정보를 추출합니다."""
    job_info = {
        "회사": "N/A",
        "제목": "N/A",
        "경력": "N/A",
        "근무형태": "N/A",
        "학력": "N/A",
        "근무지역": "N/A",
        "링크": "N/A",
    }

    # 링크
    href = job_item.get('href')
    if href:
        job_info["링크"] = f"https://zighang.com{href}"

    # 회사
    company_tag = job_item.select_one("div.ds-web-summary > span")
    if company_tag:
        job_info["회사"] = company_tag.get_text(strip=True)

    # 제목
    title_tag = job_item.select_one("p.ds-web-title2")
    if title_tag:
        job_info["제목"] = title_tag.get_text(strip=True)

    # 기타 정보 (경력, 근무형태, 학력, 근무지역)
    other_containers = job_item.select("div.ds-web-summary")
    if len(other_containers) > 1:
        details_container = other_containers[1]
        all_texts = [text.strip() for text in details_container.stripped_strings]
        details = [text for text in all_texts if text != '·']
        
        job_info['경력'] = details[0] if len(details) > 0 else "N/A"
        job_info['근무형태'] = details[1] if len(details) > 1 else "N/A"
        job_info['학력'] = details[2] if len(details) > 2 else "N/A"
        job_info['근무지역'] = details[3] if len(details) > 3 else "N/A"

    return job_info

def filter_and_extract_jobs():
    """웹사이트에서 필터링을 적용하고 채용 정보를 추출하여 Excel 파일로 저장합니다."""
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.implicitly_wait(5)

    try:
        # --- 웹사이트 열기 ---
        driver.get("https://zighang.com/ai")

        # --- 필터 버튼 클릭 ---
        filter_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='필터 임시 해제']"))
        )
        
        max_attempts = 5
        for attempt in range(max_attempts):
            print(f"필터 버튼 클릭 시도: {attempt + 1}회")
            filter_button.click()
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.flex.w-full.flex-col.gap-10.px-5.py-5"))
                )
                print("필터 내용이 성공적으로 화면에 출력되었습니다.")
                break
            except TimeoutException:
                print("필터 내용이 나타나지 않았습니다. 다시 시도합니다.")
                time.sleep(1)
        else:
            print(f"최대 시도 횟수 {max_attempts}회를 초과하여 필터 내용을 확인할 수 없었습니다.")
            return

        time.sleep(1)

        # --- 지역 옵션으로 스크롤 ---
        try:
            location_section = driver.find_element(By.XPATH, "//section[div/span[text()='지역']]")
            ActionChains(driver).move_to_element(location_section).perform()
            print("지역 옵션이 보이도록 스크롤합니다.")
        except NoSuchElementException:
            print("지역 옵션 섹션을 찾을 수 없어 스크롤할 수 없습니다.")
        
        time.sleep(2)

        # --- 학력 조건 선택 ---
        print("모든 학력 조건을 선택합니다.")
        education_levels = ['학력 무관', '고졸', '초대졸', '학사']
        for level in education_levels:
            try:
                education_section = driver.find_element(By.XPATH, "//section[./div/span[text()='학력 조건']]")
                education_button = education_section.find_element(By.XPATH, f".//button[normalize-space()='{level}']")
                driver.execute_script("arguments[0].click();", education_button)
                print(f"학력 조건 '{level}' 선택 완료.")
                time.sleep(0.5)
            except NoSuchElementException:
                print(f"학력 조건 '{level}' 버튼을 찾을 수 없었습니다.")
            except Exception as e:
                print(f"학력 조건 '{level}' 클릭 중 오류 발생: {e}")

        time.sleep(2)

        # --- 경력 슬라이더 조작 ---
        print("경력 슬라이더 조작을 시작합니다.")
        try:
            slider_handle_2 = driver.find_element(By.CSS_SELECTOR, ".MuiSlider-thumb[data-index='1']")
            slider_track = driver.find_element(By.CSS_SELECTOR, ".MuiSlider-rail")
            
            track_width = slider_track.size['width']
            track_start_x = slider_track.location['x']
            handle_start_x = slider_handle_2.location['x']

            target_x = track_start_x + (track_width * 0.225)
            x_offset = target_x - handle_start_x

            ActionChains(driver).drag_and_drop_by_offset(slider_handle_2, x_offset, 0).perform()
            print("두 번째 슬라이더 핸들을 3년차(22.5%) 지점으로 이동했습니다.")
        except NoSuchElementException:
            print("경력 슬라이더를 찾을 수 없습니다.")

        time.sleep(2)

        # --- '공고 보기' 버튼 클릭 ---
        print("'공고 보기' 버튼을 클릭합니다.")
        try:
            view_jobs_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., '개 공고 보기')]"))
            )
            view_jobs_button.click()
            print("'공고 보기' 버튼 클릭 완료.")
        except TimeoutException:
            print("오류: '공고 보기' 버튼을 20초 내에 찾거나 클릭할 수 없었습니다.")
            return

        # --- 무한 스크롤 처리 ---
        print("모든 채용 공고를 로드하기 위해 페이지를 스크롤합니다...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 새 콘텐츠 로드 대기
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("페이지 끝에 도달했습니다.")
                break
            last_height = new_height

        # --- 정보 추출 및 저장 ---
        print("채용 공고 정보 추출을 시작합니다.")
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")

        job_items = soup.select('a[href^="/recruitment/"]')
        
        if not job_items:
            print("추출할 채용 공고가 없습니다.")
            return

        print(f"{len(job_items)}개의 채용 공고를 찾았습니다.")
        extracted_data = []
        for item in job_items:
            job_info = get_job_info(item)
            extracted_data.append(job_info)

        if extracted_data:
            processed_df = pd.DataFrame(extracted_data)
            cols = ["회사", "제목", "경력", "근무형태", "학력", "근무지역", "링크"]
            processed_df = processed_df[cols]
            
            today = date.today()
            formatted_date = today.strftime("%Y-%m-%d")
            output_filename = f'sheets/ai_jobs_captured_list_{formatted_date}.xlsx'
            
            processed_df.to_excel(output_filename, index=False)
            
            print(f"데이터 처리가 완료되었습니다. 결과는 '{output_filename}' 파일에 저장되었습니다.")
            print("--- 상위 5개 결과 ---")
            print(processed_df.head().to_string())

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

    finally:
        print("10초 후 브라우저를 닫습니다.")
        time.sleep(10)
        driver.quit()

if __name__ == "__main__":
    filter_and_extract_jobs()