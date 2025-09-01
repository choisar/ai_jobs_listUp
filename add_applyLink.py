import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
from datetime import date

today = date.today()
formatted_date = today.strftime("%Y-%m-%d")

# 1. 엑셀 파일 읽기
input_filename = f'sheets/list_in_major_corp_{formatted_date}.xlsx'

try:
    df = pd.read_excel(input_filename)
except FileNotFoundError:
    print(f"'{input_filename}' 파일을 찾을 수 없습니다. 파일 이름을 확인해주세요.")
    exit()

# 지원 링크 결과를 저장할 데이터프레임 생성
result_df = pd.DataFrame({"링크": df["링크"], "지원 링크": ["추출 실패"] * len(df)})


driver = webdriver.Chrome()
for index, row in df.iterrows():

    original_link = row["링크"]
    print(f"처리 중 ({index + 1}/{len(df)}): {original_link}")

    try:
        driver.get(original_link)
        wait = WebDriverWait(driver, 20)
        wait.until(
            lambda driver: driver.execute_script(
                "return document.readyState === 'complete'"
            )
        )
        apply_button = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//button[contains(@class, 'bg-primary') and contains(., '지원하기')]",
                )
            )
        )

        original_window = driver.current_window_handle
        driver.execute_script("arguments[0].click();", apply_button)
        wait.until(EC.number_of_windows_to_be(2))

        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                break

        time.sleep(1)
        apply_page_url = driver.current_url
        result_df.at[index, "지원 링크"] = apply_page_url
        print(f"  -> 지원 링크: {apply_page_url}")

        driver.close()
        driver.switch_to.window(original_window)

    except TimeoutException:
        print(f"  -> '지원하기' 버튼을 찾을 수 없거나 시간 초과.")
    except Exception as e:
        print(f"  -> 처리 중 예상치 못한 오류 발생: {type(e).__name__} - {e}")

driver.quit()

# 4. 결과 저장
final_df = df.merge(result_df, on="링크", how="left")
output_filename = f'sheets/list_with_applyLink_{formatted_date}.xlsx'
final_df.to_excel(output_filename, index=False)
print(f"\n작업 완료! 결과가 '{output_filename}' 파일에 저장되었습니다.")
