import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import os
import time
import json
import re
import random
import shutil
import tempfile

BASE_USER_DATA_DIR = "/home/user/snap/chromium/common/chromium"

def create_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={BASE_USER_DATA_DIR}")
    options.add_argument("--disk-cache-dir=/tmp/chrome-tmp")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0")
    driver = uc.Chrome(options=options)
    return driver

max_scrolls = 30

def main_scraper(target_date, max_scrolls, driver):
    print(f"开始抓取 {target_date} 的推文基本信息...")
    search_url = f"https://twitter.com/search?q=%23dog%20since%3A{target_date.isoformat()}&f=live"

    retries = 2
    for attempt in range(retries):
        try:
            driver.get(search_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
            )
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"加载失败，尝试重试（{attempt + 1}）...")
                time.sleep(5)
                driver.refresh()
            else:
                print("页面加载失败，跳过。")
                return []

    seen = set()
    tweets_basic = []

    last_count = 0
    stable_scrolls = 0

    for scroll_idx in range(max_scrolls):
        driver.execute_script("window.scrollBy(0, 2000);")
        time.sleep(random.uniform(0.5, 1.5))

        tweet_cards = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        if not tweet_cards:
            print("未找到推文，结束滚动")
            break

        for card in tweet_cards:
            try:
                timestamp = card.find_element(By.TAG_NAME, "time").get_attribute("datetime")
                tweet_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.000Z").date()
                #if tweet_date != target_date:
                    #continue

                tweet_url = ""
                links = card.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href and re.search(r"https://(twitter|x)\.com/[^/]+/status/\d+$", href):
                        tweet_url = href
                        break
                if not tweet_url or tweet_url in seen:
                    continue

                username = card.find_element(By.XPATH, ".//div[@dir='ltr']//span").text
                content = card.find_element(By.XPATH, ".//div[@data-testid='tweetText']").text

                tweets_basic.append({
                    "username": username,
                    "timestamp": timestamp,
                    "content": content,
                    "url": tweet_url
                })
                seen.add(tweet_url)
            except Exception:
                continue

        print(f"滚动次数 {scroll_idx + 1}/{max_scrolls}，累计推文数: {len(tweets_basic)}")

        if len(tweets_basic) == last_count:
            stable_scrolls += 1
        else:
            stable_scrolls = 0
        last_count = len(tweets_basic)

        if stable_scrolls >= 6:
            print("检测到连续 3 次滚动无新增内容，提前结束")
            break

    return tweets_basic

def fetch_replies(tweet, driver, max_depth=2, current_depth=1):
    try:
        driver.get(tweet["url"])
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
        )
        time.sleep(random.uniform(0.3, 0.6))

        replies = []

        def parse_replies():
            cards = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            parsed = []
            for card in cards[1:]:
                try:
                    username = card.find_element(By.XPATH, ".//div[@dir='ltr']//span").text
                    content = card.find_element(By.XPATH, ".//div[@data-testid='tweetText']").text
                    timestamp = card.find_element(By.TAG_NAME, "time").get_attribute("datetime")
                    parsed.append({
                        "username": username,
                        "timestamp": timestamp,
                        "content": content,
                        "replies": []
                    })
                except:
                    continue
            return parsed

        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 2000);")
            time.sleep(0.5)

        replies = parse_replies()

        if current_depth < max_depth:
            more_buttons = driver.find_elements(By.XPATH, "//div[contains(text(), 'Show more replies')]")
            for btn in more_buttons:
                try:
                    driver.execute_script("arguments[0].scrollIntoView();", btn)
                    btn.click()
                    time.sleep(random.uniform(0.5, 0.9))
                except:
                    continue

            for _ in range(2):
                driver.execute_script("window.scrollBy(0, 2000);")
                time.sleep(0.5)

            deeper_replies = parse_replies()
            for i in range(min(len(replies), len(deeper_replies))):
                replies[i]["replies"] = deeper_replies[i].get("replies", [])

        tweet["replies"] = replies
        print(f"{tweet['url']} 收集到 {len(replies)} 条一级回复")
        return tweet

    except Exception as e:
        print(f"抓取失败：{tweet['url']} 错误：{e}")
        tweet["replies"] = []
        return tweet

if __name__ == "__main__":
    os.makedirs("/tmp/chrome-tmp", exist_ok=True)
    target_date = datetime.utcnow().date() - timedelta(days=7)
    driver = create_driver()

    try:
        tweets_basic = main_scraper(target_date, max_scrolls=max_scrolls, driver=driver)
        print(f"主进程抓取到 {len(tweets_basic)} 条推文，开始抓取回复...")

        tweets_full = []
        for tweet in tweets_basic:
            full_tweet = fetch_replies(tweet, driver)
            tweets_full.append(full_tweet)

        with open("tweets_with_replies.json", "w", encoding="utf-8") as f:
            json.dump(tweets_full, f, ensure_ascii=False, indent=2)

        print(f"抓取完成，共 {len(tweets_full)} 条推文及其回复。")
    finally:
        driver.quit()
