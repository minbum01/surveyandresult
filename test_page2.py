"""
page=2 크롤링 테스트 - 목록에서 제목+조회수, 각 글에서 요약정보+본문
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import json

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=options)

results = []

try:
    # 1단계: page=2 목록에서 제목 + 조회수 + 링크 수집
    url = "https://gosi.hackers.com/html/mmove.htm?id=exam_passnote_new&m=&cate=&cate2=&cate3=&cate4=&cate5=&cate6=&idx=&user_id=&search_opt=&search_txt=&hb_year=&page=2"
    driver.get(url)
    time.sleep(5)

    print("=== page=2 목록 크롤링 ===\n")
    posts = []
    # page 2+: tr[2] ~ tr[16]
    for i in range(2, 17):
        try:
            # 제목 + 링크
            title_xpath = f'//*[@id="wrapper"]/div[4]/div[2]/div[8]/div[1]/div/div/table/tbody/tr[{i}]/td[1]/a'
            title_elem = driver.find_element(By.XPATH, title_xpath)
            title = title_elem.text.strip()
            href = title_elem.get_attribute('href')

            # 조회수
            view_xpath = f'//*[@id="wrapper"]/div[4]/div[2]/div[8]/div[1]/div/div/table/tbody/tr[{i}]/td[3]'
            view_elem = driver.find_element(By.XPATH, view_xpath)
            views = view_elem.text.strip()

            posts.append({
                'tr': i,
                'title': title,
                'views': views,
                'href': href
            })
            print(f"tr[{i}] | 조회수: {views:>6} | {title[:60]}")
        except Exception as e:
            print(f"tr[{i}] | 실패: {e}")

    print(f"\n총 {len(posts)}개 수집\n")

    # 2단계: 각 게시글 들어가서 요약정보 + 본문 수집
    for idx, post in enumerate(posts):
        print(f"\n--- [{idx+1}/{len(posts)}] {post['title'][:50]} ---")
        driver.get(post['href'])
        time.sleep(4)

        # 요약정보
        summary_data = {}
        try:
            summary_xpath = '//*[@id="wrapper"]/div[4]/div[2]/div/div/div[1]/div/div/div[1]'
            summary_elem = driver.find_element(By.XPATH, summary_xpath)
            summary_text = summary_elem.text.strip()
            # "카테고리 : 값\n응시시험 : 값" 형태 파싱
            for line in summary_text.split('\n'):
                if ':' in line:
                    key, val = line.split(':', 1)
                    summary_data[key.strip()] = val.strip()
            print(f"  요약: {summary_data}")
        except Exception as e:
            print(f"  요약 실패: {e}")

        # 본문
        content = ""
        try:
            content_xpath = '//*[@id="wrapper"]/div[4]/div[2]/div/div/div[2]'
            content_elem = driver.find_element(By.XPATH, content_xpath)
            content = content_elem.text.strip()
            print(f"  본문: {content[:100]}...")
        except Exception as e:
            print(f"  본문 실패: {e}")

        results.append({
            'title': post['title'],
            'views': post['views'],
            'url': post['href'],
            'summary': summary_data,
            'content': content
        })

    # 저장
    with open('test_page2_result.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n\n=== 완료: {len(results)}개 저장 → test_page2_result.json ===")

finally:
    driver.quit()
