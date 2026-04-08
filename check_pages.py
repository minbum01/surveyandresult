"""
총 페이지 수 / 게시글 수 확인
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import re

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=options)

try:
    # 마지막 페이지 찾기: 큰 페이지 번호로 시도
    for test_page in [100, 500, 1000, 2000]:
        url = f"https://gosi.hackers.com/html/mmove.htm?id=exam_passnote_new&m=&cate=&cate2=&cate3=&cate4=&cate5=&cate6=&idx=&user_id=&search_opt=&search_txt=&hb_year=&page={test_page}"
        driver.get(url)
        time.sleep(4)

        # 게시글이 있는지 확인
        posts = []
        for i in range(2, 17):
            try:
                xpath = f'//*[@id="wrapper"]/div[4]/div[2]/div[8]/div[1]/div/div/table/tbody/tr[{i}]/td[1]/a'
                elem = driver.find_element(By.XPATH, xpath)
                title = elem.text.strip()
                if title:
                    posts.append(title)
            except:
                pass

        print(f"page={test_page}: {len(posts)}개 게시글 발견")
        if posts:
            print(f"  첫 글: {posts[0][:60]}")

        # 페이징 영역에서 페이지 번호 찾기
        try:
            all_links = driver.find_elements(By.TAG_NAME, 'a')
            max_page = 0
            for link in all_links:
                href = link.get_attribute('href') or ''
                if 'exam_passnote_new' in href and 'page=' in href:
                    match = re.search(r'page=(\d+)', href)
                    if match:
                        p = int(match.group(1))
                        if p > max_page:
                            max_page = p
            print(f"  이 페이지에서 보이는 최대 page 번호: {max_page}")
        except:
            pass
        print()

finally:
    driver.quit()
