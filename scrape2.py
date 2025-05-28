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


# Chrome 用户数据目录
BASE_USER_DATA_DIR = "/home/user/.config/google-chrome/Default"


def create_driver():
    # 清理可能的临时文件
    os.system("pkill -f chrome")  # 确保没有残留的Chrome进程
    os.system("rm -rf /tmp/chrome-tmp")  # 清理缓存目录
    
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={BASE_USER_DATA_DIR}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--disk-cache-dir=/tmp/chrome-tmp")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # 简化初始配置
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    
    # 获取准确的Chrome版本
    try:
        chrome_version = subprocess.getoutput("/usr/bin/google-chrome --version").split()[2].split('.')[0]
    except:
        chrome_version = 137  # 默认版本
    
    retries = 3
    for attempt in range(retries):
        try:
            # 使用更稳定的初始化方式
            driver = uc.Chrome(
                options=options,
                browser_executable_path="/usr/bin/google-chrome",
                version_main=int(chrome_version),
                service_log_path=None,  # 禁用日志避免干扰
                use_subprocess=True,  # 使用子进程模式
                suppress_welcome=True,  # 禁止欢迎页面
                headless=False,
                enable_cdp_events=False  # 禁用CDP事件
            )
            
            # 验证连接
            driver.get("about:blank")
            return driver
            
        except json.JSONDecodeError:
            print(f"JSON解析错误，重试中 ({attempt + 1}/{retries})...")
            time.sleep(2)
            os.system("pkill -f chrome")  # 确保清理残留进程
            continue
            
        except Exception as e:
            print(f"初始化失败: {str(e)[:200]}")
            raise

    raise RuntimeError("无法初始化Chrome驱动，请检查浏览器安装")



def is_within_date_range(tweet_date, start_date, end_date):
    """检查推文日期是否在指定范围内"""
    return start_date <= tweet_date <= end_date

def main_scraper(tag, max_scrolls, driver, start_date, end_date):
    print(f"开始爬取 #{tag} 相关的推文，日期范围: {start_date} 至 {end_date}...")
    search_url = f"https://x.com/search?q={tag}&src=typed_query"

    retries = 2
    for attempt in range(retries):
        try:
            driver.get(search_url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
            )
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"页面加载失败，重试中 ({attempt + 1})...")
                time.sleep(5)
                driver.refresh()
            else:
                print("页面加载失败，跳过")
                return []

    seen = set()
    all_tweets = []
    filtered_tweets = []

    last_count = 0
    stable_scrolls = 0

    for scroll_idx in range(max_scrolls):
        driver.execute_script("window.scrollBy(0, 2000);")
        time.sleep(random.uniform(0.4, 0.6))  # 增加随机延迟避免被封

        tweet_cards = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        if not tweet_cards:
            print("没有找到更多推文，停止滚动")
            break

        for card in tweet_cards:
            try:
                # 获取时间戳
                time_element = card.find_element(By.TAG_NAME, "time")
                timestamp = time_element.get_attribute("datetime")
                tweet_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.000Z").date()

                # 获取推文URL
                tweet_url = ""
                links = card.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href and re.search(r"https://x\.com/[^/]+/status/\d+$", href):
                        tweet_url = href
                        break
                
                if not tweet_url or tweet_url in seen:
                    continue

                # 获取用户名和内容
                username = card.find_element(By.XPATH, ".//div[@dir='ltr']//span").text
                try:
                    content = card.find_element(By.XPATH, ".//div[@lang]").text
                except:
                    print(f"处理推文时出错: {e}")
                    print("可能的 tweet 元素 HTML：", card.get_attribute('outerHTML')[:500])
                    content = ""

                tweet_data = {
                    "username": username,
                    "timestamp": timestamp,
                    "date": str(tweet_date),
                    "content": content,
                    "url": tweet_url,
                    "replies": []
                }

                all_tweets.append(tweet_data)
                seen.add(tweet_url)

                # 如果推文在日期范围内，添加到筛选列表
                if is_within_date_range(tweet_date, start_date, end_date):
                    filtered_tweets.append(tweet_data)

            except Exception as e:
                print(f"处理推文时出错: {e}")
                continue

        print(f"滚动 {scroll_idx + 1}/{max_scrolls}, 总推文数: {len(all_tweets)}, 符合日期范围的推文: {len(filtered_tweets)}")

        # 如果没有新推文，增加稳定计数器
        if len(all_tweets) == last_count:
            stable_scrolls += 1
        else:
            stable_scrolls = 0
        last_count = len(all_tweets)

        # 如果连续5次滚动没有新内容，提前停止
        if stable_scrolls >= 5:
            print("连续5次滚动没有新内容，提前停止")
            break

    return filtered_tweets

def fetch_replies(tweet, driver, max_depth=2, current_depth=1, max_replies_per_level=5):
    try:
        print(f"\n=== 开始获取回复 (深度 {current_depth}/{max_depth}) ===")
        print(f"父推文URL: {tweet['url']}")
        
        driver.get(tweet["url"])
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
        )
        time.sleep(random.uniform(1.0, 1.5))

        def extract_tweet_data(card):
            try:
                # 提取用户名 (从链接获取准确用户名)
                username_elem = card.find_element(By.XPATH, ".//div[@data-testid='User-Name']//a")
                username = username_elem.get_attribute("href").split("/")[-1]
                
                # 提取内容
                content_elem = card.find_elements(By.XPATH, ".//div[@data-testid='tweetText']")
                content = content_elem[0].text if content_elem else ""
                
                # 提取时间戳和status_id
                time_elem = card.find_elements(By.TAG_NAME, "time")
                if not time_elem:
                    return None
                
                timestamp = time_elem[0].get_attribute("datetime")
                
                # 从推文卡片的链接获取准确的status_id
                links = card.find_elements(By.XPATH, ".//a[contains(@href, '/status/')]")
                status_id = None
                for link in links:
                    href = link.get_attribute("href")
                    match = re.search(r'/status/(\d+)', href)
                    if match:
                        status_id = match.group(1)
                        break
                
                if not status_id:
                    print("无法从推文卡片提取status_id")
                    return None
                
                # 构建准确的推文URL
                tweet_url = f"https://x.com/{username}/status/{status_id}"
                
                return {
                    "username": username,
                    "timestamp": timestamp,
                    "date": str(datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.000Z").date()),
                    "content": content,
                    "url": tweet_url,
                    "replies": []
                }
            except Exception as e:
                print(f"提取推文数据出错: {str(e)[:100]}...")
                return None

        def smart_scroll_and_parse():
            all_replies = []
            seen_urls = set()
            last_count = 0
            stable_scrolls = 0

            for scroll_attempt in range(30):
                # 获取当前可见的推文卡片
                cards = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                
                # 关键修改：始终跳过第一个推文（父推文）
                valid_cards = cards[1:] if current_depth == 0 else cards
                
                print(f"滚动 {scroll_attempt}: 找到 {len(valid_cards)} 个有效推文卡片")
                
                new_replies = []
                for card in valid_cards:
                    tweet_data = extract_tweet_data(card)
                    if tweet_data and tweet_data['url'] not in seen_urls:
                        new_replies.append(tweet_data)
                        seen_urls.add(tweet_data['url'])
                
                if new_replies:
                    print(f"发现 {len(new_replies)} 条新回复")
                    all_replies.extend(new_replies)
                    stable_scrolls = 0
                else:
                    stable_scrolls += 1
                    print(f"没有发现新回复 (稳定计数器: {stable_scrolls})")

                # 滚动页面
                driver.execute_script("window.scrollBy(0, 2000);")
                time.sleep(random.uniform(0.7, 1.3))

                # 停止条件
                if stable_scrolls >= 2:
                    print("连续2次滚动没有发现新内容，停止滚动")
                    break

            return all_replies

        # 获取当前层的回复
        all_replies = smart_scroll_and_parse()
        print(f"总共获取 {len(all_replies)} 条{'' if current_depth == 0 else '子'}回复")

        # 递归获取深层回复
        if current_depth < max_depth:
            print(f"\n=== 开始递归获取深层回复 (深度 {current_depth + 1}/{max_depth}) ===")
            
            # 只有从二级回复开始才限制数量
            if current_depth >= 1:
                if len(all_replies) > max_replies_per_level:
                    print(f"从 {len(all_replies)} 条回复中筛选前 {max_replies_per_level} 条进行深层爬取")
                    replies_to_process = all_replies[:max_replies_per_level]
                    other_replies = all_replies[max_replies_per_level:]
                    
                    # 为不处理的回复保留空replies数组
                    for reply in other_replies:
                        reply['replies'] = []
                else:
                    replies_to_process = all_replies
                    other_replies = []
            else:
                # 一级回复全部处理
                replies_to_process = all_replies
                other_replies = []
            
            for reply_idx, reply in enumerate(replies_to_process):
                try:
                    print(f"\n处理第 {reply_idx + 1}/{len(replies_to_process)} 条回复 | URL: {reply['url']}")
                    
                    # 递归获取回复
                    nested_replies = fetch_replies(
                        {"url": reply["url"], "replies": []},
                        driver,
                        max_depth,
                        current_depth + 1,
                        max_replies_per_level
                    )
                    reply["replies"] = nested_replies["replies"] if isinstance(nested_replies, dict) else nested_replies
                    print(f"获取了 {len(reply['replies'])} 条深层回复 | 父回复: {reply['url']}")
                    
                    # 随机暂停
                    if (reply_idx + 1) % 15 == 0:
                        sleep_time = random.uniform(1.5, 3.5)
                        print(f"暂停 {sleep_time:.1f} 秒...")
                        time.sleep(sleep_time)
                        
                except Exception as e:
                    print(f"处理深层回复时出错: {str(e)[:200]}... | 回复URL: {reply.get('url', '无URL')}")
                    continue

            # 合并处理过的和未处理的回复
            if current_depth >= 1:
                all_replies = replies_to_process + other_replies

        tweet["replies"] = all_replies
        print(f"\n=== 完成获取回复 (深度 {current_depth}/{max_depth}) ===")
        print(f"父推文 {tweet['url']} 总共有 {len(all_replies)} 条回复")
        
        return tweet

    except Exception as e:
        print(f"\n!!! 获取回复失败 (深度 {current_depth}/{max_depth}) !!!")
        print(f"URL: {tweet.get('url', '无URL')}")
        print(f"错误: {str(e)[:200]}...")
        tweet["replies"] = []
        return tweet

    

   



if __name__ == "__main__":
    # 创建临时目录
    os.makedirs("/tmp/chrome-tmp", exist_ok=True)
    
    # 设置搜索参数
    tag_to_search = "dog"  # 可以改为任何你想搜索的标签
    max_scrolls = 3       # 最大滚动次数
    
    # 设置日期范围 (YYYY-MM-DD)
    start_date = datetime.strptime("2025-05-01", "%Y-%m-%d").date()
    end_date = datetime.strptime("2025-05-28", "%Y-%m-%d").date()
    
    driver = create_driver()

    try:
        # 第一步：爬取所有推文并筛选日期
        filtered_tweets = main_scraper(
            tag=tag_to_search,
            max_scrolls=max_scrolls,
            driver=driver,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"主爬取完成，找到 {len(filtered_tweets)} 条符合日期范围的推文，开始获取回复...")

        # 第二步：获取符合条件推文的回复
        tweets_with_replies = []
        for i, tweet in enumerate(filtered_tweets):
            full_tweet = fetch_replies(tweet, driver)
            tweets_with_replies.append(full_tweet)
            print(f"进度: {i+1}/{len(filtered_tweets)}")
            
            # 每处理5条推文后随机暂停
            if (i + 1) % 8 == 0:
                sleep_time = random.uniform(2, 5)
                print(f"随机暂停 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)

        # 保存结果
        output_file = f"tweets_{tag_to_search}_{start_date}_{end_date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tweets_with_replies, f, ensure_ascii=False, indent=2)

        print(f"爬取完成! 结果已保存到 {output_file}")
        
    finally:
        driver.quit()