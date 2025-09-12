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

# --- Part 1: Scraper Functions ---


def get_job_info(job_item):
    """Extracts information from a single job posting item (BeautifulSoup Tag)."""
    job_info = {
        "회사": "N/A",
        "제목": "N/A",
        "경력": "N/A",
        "근무형태": "N/A",
        "학력": "N/A",
        "근무지역": "N/A",
        "링크": "N/A",
    }
    if href := job_item.get("href"):
        job_info["링크"] = f"https://zighang.com{href}"
    if company_tag := job_item.select_one("div.ds-web-summary > span"):
        job_info["회사"] = company_tag.get_text(strip=True)
    if title_tag := job_item.select_one("p.ds-web-title2"):
        job_info["제목"] = title_tag.get_text(strip=True)
    if len(other_containers := job_item.select("div.ds-web-summary")) > 1:
        details_container = other_containers[1]
        all_texts = [text.strip() for text in details_container.stripped_strings]
        details = [text for text in all_texts if text != "·"]
        job_info["경력"] = details[0] if len(details) > 0 else "N/A"
        job_info["근무형태"] = details[1] if len(details) > 1 else "N/A"
        job_info["학력"] = details[2] if len(details) > 2 else "N/A"
        job_info["근무지역"] = details[3] if len(details) > 3 else "N/A"
    return job_info


def scrape_all_jobs():
    """Applies filters on the website and scrapes all job postings."""
    print("--- 1단계: 모든 채용 공고 스크래핑 시작 ---")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.implicitly_wait(5)

    try:
        driver.get("https://zighang.com/ai")
        filter_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[aria-label='필터 임시 해제']")
            )
        )
        for attempt in range(5):
            filter_button.click()
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.flex.w-full.flex-col.gap-10.px-5.py-5")
                    )
                )
                print("필터 내용 표시 성공.")
                break
            except TimeoutException:
                print(f"필터 버튼 클릭 시도 {attempt + 1} 실패. 재시도...")
                time.sleep(1)
        else:
            print("필터 내용을 열 수 없습니다.")
            return None

        time.sleep(1)
        
        # --- 지역 옵션으로 스크롤 ---
        try:
            location_section = driver.find_element(By.XPATH, "//section[div/span[text()='지역']]")
            ActionChains(driver).move_to_element(location_section).perform()
            print("지역 옵션이 보이도록 스크롤합니다.")
        except NoSuchElementException:
            print("지역 옵션 섹션을 찾을 수 없어 스크롤할 수 없습니다.")
        
        time.sleep(2)
        
        print("학력 조건 선택 중...")
        for level in ["학력 무관", "고졸", "초대졸", "학사"]:
            try:
                section = driver.find_element(
                    By.XPATH, "//section[./div/span[text()='학력 조건']]"
                )
                btn = section.find_element(
                    By.XPATH, f".//button[normalize-space()='{level}']"
                )
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
            except Exception as e:
                print(f"'{level}' 선택 중 오류: {e}")

        time.sleep(2)
        print("경력 슬라이더 조작 중...")
        try:
            handle = driver.find_element(
                By.CSS_SELECTOR, ".MuiSlider-thumb[data-index='1']"
            )
            track = driver.find_element(By.CSS_SELECTOR, ".MuiSlider-rail")
            offset = (
                track.location["x"] + (track.size["width"] * 0.225)
            ) - handle.location["x"]
            ActionChains(driver).drag_and_drop_by_offset(handle, offset, 0).perform()
            print("경력 슬라이더를 3년차로 설정했습니다.")
        except Exception as e:
            print(f"슬라이더 조작 중 오류: {e}")

        time.sleep(2)
        print("'공고 보기' 버튼 클릭 중...")
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., '개 공고 보기')]")
            )
        ).click()

        print("모든 공고를 로드하기 위해 스크롤합니다...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("페이지 끝에 도달했습니다.")
                break
            last_height = new_height

        print("HTML에서 정보 추출 중...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        job_items = soup.select('a[href^="/recruitment/"]')
        if not job_items:
            print("추출할 채용 공고가 없습니다.")
            return None

        print(f"{len(job_items)}개의 채용 공고를 찾았습니다.")
        extracted_data = [get_job_info(item) for item in job_items]

        if extracted_data:
            processed_df = pd.DataFrame(extracted_data)
            cols = ["회사", "제목", "경력", "근무형태", "학력", "근무지역", "링크"]
            print("스크래핑 완료.")
            return processed_df[cols]

    except Exception as e:
        print(f"스크래핑 중 오류 발생: {e}")
    finally:
        driver.quit()
    return None


# --- Part 2: Filter Function ---


def filter_major_corps(jobs_df):
    """Filters the job DataFrame to include only major corporations."""
    print("--- 2단계: 대기업 공고 필터링 시작 ---")
    if jobs_df is None or jobs_df.empty:
        print("필터링할 데이터가 없습니다.")
        return None
    try:
        corp_list_path = "sheets/corp_list.xlsx"
        df_corpList = pd.read_excel(corp_list_path)
        print(f"'{corp_list_path}'에서 대기업 목록을 불러왔습니다.")

        jobs_df["회사_clean"] = jobs_df["회사"].str.replace(" ", "", regex=False)
        df_corpList["회사_clean"] = df_corpList["회사"].str.replace(
            " ", "", regex=False
        )

        df_major = jobs_df[jobs_df["회사_clean"].isin(df_corpList["회사_clean"])].copy()
        df_major.drop(columns=["회사_clean"], inplace=True)
        df_major.reset_index(drop=True, inplace=True)

        print(f"필터링 완료. {len(df_major)}개의 대기업 공고를 찾았습니다.")
        return df_major
    except FileNotFoundError:
        print(f"'{corp_list_path}' 파일을 찾을 수 없습니다.")
        return None
    except Exception as e:
        print(f"필터링 중 오류 발생: {e}")
        return None


# --- Part 3: Apply Link Fetcher Function ---


def get_apply_links(major_corps_df):
    """Fetches the direct application link for each job posting."""
    print("--- 3단계: 최종 지원 링크 추출 시작 ---")
    if major_corps_df is None or major_corps_df.empty:
        print("지원 링크를 추출할 데이터가 없습니다.")
        return None

    result_df = pd.DataFrame(
        {
            "링크": major_corps_df["링크"],
            "지원 링크": ["추출 실패"] * len(major_corps_df),
        }
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.maximize_window()  # 브라우저 창을 전체화면으로 설정
    original_window = driver.current_window_handle

    try:
        for index, row in major_corps_df.iterrows():
            original_link = row["링크"]
            print(f"처리 중 ({index + 1}/{len(major_corps_df)}): {original_link}")

            # Switch to the main window and open the link
            driver.switch_to.window(original_window)
            driver.get(original_link)

            try:
                wait = WebDriverWait(driver, 20)
                apply_button = wait.until(
                    EC.element_to_be_clickable(
                        (
                            By.XPATH,
                            "//button[contains(@class, 'bg-primary') and contains(., '지원하기')]",
                        )
                    )
                )

                initial_windows = set(driver.window_handles)
                driver.execute_script("arguments[0].click();", apply_button)

                # Wait for a new window to appear
                wait.until(lambda d: len(initial_windows) < len(d.window_handles))
                new_window_handle = (set(driver.window_handles) - initial_windows).pop()
                driver.switch_to.window(new_window_handle)

                time.sleep(1)  # Allow URL to stabilize
                apply_page_url = driver.current_url
                result_df.at[index, "지원 링크"] = apply_page_url
                print(f"  -> 지원 링크: {apply_page_url}")

            except Exception as e:
                print(f"  -> 처리 중 오류: {e}")

            finally:
                # Clean up extra windows, ensuring only the original one remains
                current_handles = driver.window_handles
                if len(current_handles) > 1:
                    for handle in current_handles:
                        if handle != original_window:
                            driver.switch_to.window(handle)
                            driver.close()
                driver.switch_to.window(original_window)

    finally:
        driver.quit()

    final_df = major_corps_df.merge(result_df, on="링크", how="left")
    print("지원 링크 추출 완료.")
    return final_df


# --- Main Execution ---

if __name__ == "__main__":
    all_jobs_df = scrape_all_jobs()
    major_corps_df = filter_major_corps(all_jobs_df)
    final_df_with_links = get_apply_links(major_corps_df)

    if final_df_with_links is not None and not final_df_with_links.empty:
        today = date.today()
        formatted_date = today.strftime("%Y-%m-%d")
        output_filename = f"sheets/list_with_applyLink_{formatted_date}.xlsx"
        final_df_with_links.to_excel(output_filename, index=False)
        print(
            f"--- 모든 작업 완료! 최종 결과가 '{output_filename}'에 저장되었습니다. ---"
        )
        print(final_df_with_links.head().to_string())
    else:
        print("최종 결과 데이터가 없어 파일을 저장하지 않았습니다.")
