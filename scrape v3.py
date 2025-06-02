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
import subprocess
from fake_useragent import UserAgent

# Chrome 用户数据目录
BASE_USER_DATA_DIR = "/home/user/.config/google-chrome/Default"

class RequestLimiter:
    def __init__(self):
        self.last_request_time = 0
        self.request_count = 0
        self.reset_time = time.time() + 3600  # 每小时重置计数器
        
    def check_limit(self):
        current = time.time()
        # 每分钟不超过60次请求
        if self.request_count > 60 and current < self.last_request_time + 60:
            wait = (self.last_request_time + 20) - current
            print(f"⚠️ 请求过于频繁，等待 {wait:.1f}秒")
            time.sleep(wait + random.uniform(1, 3))
            self.request_count = 0
        
        # 每小时重置计数器
        if current > self.reset_time:
            self.reset_time = current + 3600
            self.request_count = 0
            
        self.last_request_time = current
        self.request_count += 1

def random_delay(min_sec=1.5, max_sec=5.0):
    """随机延迟"""
    delay = random.uniform(min_sec, max_sec)
    if random.random() < 0.02:  # 6%概率插入长延迟
        delay += random.uniform(7, 10)
    time.sleep(delay)

def get_random_useragent():
    """动态User-Agent"""
    ua = UserAgent()
    return ua.chrome

def create_stealth_driver():
    # 清理可能的临时文件
    #os.system("pkill -f chrome")  # 确保没有残留的Chrome进程
    os.system("rm -rf /tmp/chrome-tmp")  # 清理缓存目录
    
    retries = 3
    for attempt in range(retries):
        try:
            # 每次尝试都创建新的ChromeOptions对象
            options = uc.ChromeOptions()
            
            # 基本配置
            options.add_argument("--start-maximized")
            #options.add_argument(f"--user-data-dir={BASE_USER_DATA_DIR}")
            #options.add_argument("--profile-directory=Default")
            options.add_argument("--disk-cache-dir=/tmp/chrome-tmp")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # 获取Chrome版本
            try:
                chrome_version = subprocess.getoutput("/usr/bin/google-chrome --version").split()[2].split('.')[0]
            except:
                chrome_version = 137  # 默认版本

            print("尝试启动 Chrome 浏览器...")
            
            # 最小化初始化配置
            driver = uc.Chrome(
                options=options,
                browser_executable_path="/usr/bin/google-chrome",
                version_main=int(chrome_version),
            )
            print("Chrome 已成功启动")
            # 验证连接
            driver.get("about:blank")
            time.sleep(1)
            return driver
            
        except Exception as e:
            print(f"初始化失败 (尝试 {attempt + 1}/{retries}): {str(e)[:200]}")
            os.system("pkill -f chrome")
            time.sleep(2)
            continue

    raise RuntimeError("无法初始化Chrome驱动，请检查浏览器安装")

def handle_rate_limit(driver):
    """处理被封禁的情况"""
    wait_times = [300, 600, 1800]  # 5分钟, 10分钟, 30分钟
    for wait in wait_times:
        print(f"🚨 可能被限流，等待 {wait//60} 分钟...")
        time.sleep(wait)
        
        try:
            driver.get("https://x.com/about")
            if "About" in driver.title:
                print("✅ 限制已解除，继续爬取")
                return True
        except:
            continue
            
    return False

def is_within_date_range(tweet_date, start_date, end_date):
    """检查推文日期是否在指定范围内"""
    return start_date <= tweet_date <= end_date

def extract_tweet_id(url):
    """从URL中提取推文ID"""
    match = re.search(r'/status/(\d+)', url)
    return match.group(1) if match else None

def main_scraper(tag, max_scrolls, driver, start_date, end_date, limiter):
    print(f"开始爬取 #{tag} 相关的推文，日期范围: {start_date} 至 {end_date}...")
    search_url = f"https://x.com/search?q={tag}&src=typed_query"

    retries = 2
    for attempt in range(retries):
        try:
            limiter.check_limit()
            driver.get(search_url)
            WebDriverWait(driver, random.randint(15, 25)).until(
                EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
            )
            random_delay()
            break
        except Exception as e:
            if attempt < retries - 1:
                print(f"页面加载失败，重试中 ({attempt + 1}): {str(e)[:100]}...")
                random_delay(3, 8)
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
        limiter.check_limit()
        
        # 随机滚动行为
        scroll_height = random.randint(1500, 2000)
        driver.execute_script(f"window.scrollBy(0, {scroll_height});")
        random_delay(0.4, 1.2)

        tweet_cards = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        if not tweet_cards:
            print("没有找到更多推文，停止滚动")
            break

        for card in tweet_cards:
            try:
                limiter.check_limit()
                
                time_element = card.find_element(By.TAG_NAME, "time")
                timestamp = time_element.get_attribute("datetime")
                tweet_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.000Z").date()

                tweet_url = ""
                links = card.find_elements(By.TAG_NAME, "a")
                for link in links:
                    href = link.get_attribute("href")
                    if href and re.search(r"https://x\.com/[^/]+/status/\d+$", href):
                        tweet_url = href
                        break
                
                tweet_id = extract_tweet_id(tweet_url)
                if not tweet_id or tweet_id in seen:
                    continue

                username = card.find_element(By.XPATH, ".//div[@dir='ltr']//span").text
                try:
                    content = card.find_element(By.XPATH, ".//div[@lang]").text
                except Exception as e:
                    content = ""
                    print(f"提取内容出错: {str(e)[:100]}...")

                tweet_data = {
                    "id": tweet_id,
                    "username": username,
                    "timestamp": timestamp,
                    "date": str(tweet_date),
                    "content": content,
                    "url": tweet_url,
                    "replies": []
                }

                all_tweets.append(tweet_data)
                seen.add(tweet_id)

                if is_within_date_range(tweet_date, start_date, end_date):
                    filtered_tweets.append(tweet_data)

            except Exception as e:
                print(f"处理推文时出错: {str(e)[:100]}...")
                continue

        print(f"滚动 {scroll_idx + 1}/{max_scrolls}, 总推文数: {len(all_tweets)}, 符合日期范围的推文: {len(filtered_tweets)}")

        if len(all_tweets) == last_count:
            stable_scrolls += 1
            if stable_scrolls >= 3:  # 连续3次无新内容则停止
                print("连续3次滚动没有发现新内容，停止滚动")
                break
        else:
            stable_scrolls = 0
        last_count = len(all_tweets)

        # 随机阅读模式
        if random.random() < 0.2:
            read_time = random.uniform(3, 4)
            print(f"模拟阅读行为，暂停 {read_time:.1f}秒...")
            time.sleep(read_time)

    return filtered_tweets

class ReplyScraper:
    def __init__(self, driver, limiter):
        self.driver = driver
        self.limiter = limiter
        self.seen_ids = set()  # 全局已爬取的推文ID记录
        self.max_depth = 0
        self.current_depth = 0
    
    def fetch_replies(self, tweet, max_depth=2, current_depth=1, max_replies_per_level=5 ):
        if current_depth > max_depth:
            return tweet
            
        try:
            self.limiter.check_limit()
            print(f"\n=== 开始获取回复 (深度 {current_depth}/{max_depth}) ===")
            print(f"父推文URL: {tweet['url']}")
            
            tweet_id = tweet.get('id') or extract_tweet_id(tweet['url'])
            if not tweet_id:
                print("无法获取推文ID，跳过")
                return tweet
                
            if tweet_id in self.seen_ids:
                print(f"推文 {tweet_id} 已经处理过，跳过")
                return tweet
                
            self.seen_ids.add(tweet_id)
            
            # 动态修改User-Agent
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": get_random_useragent()
            })
            
            self.driver.get(tweet["url"])
            WebDriverWait(self.driver, random.randint(15, 25)).until(
                EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
            )
            random_delay()

            # 获取当前页面的所有回复
            replies = self._extract_replies_from_page(current_depth)
            print(f"初步提取 {len(replies)} 条回复 (深度 {current_depth})")
            
            # 如果当前是第一层，可能需要处理"查看更多回复"的情况
            if current_depth == 0 and len(replies) < 3:
                replies.extend(self._check_for_more_replies(current_depth))
                print(f"查看更多回复后，共 {len(replies)} 条回复")
            
            # 限制每层的回复数量
            if len(replies) > max_replies_per_level:
                print(f"从 {len(replies)} 条回复中筛选前 {max_replies_per_level} 条进行深层爬取")
                replies_to_process = replies[:max_replies_per_level]
            else:
                replies_to_process = replies
                
            # 递归获取深层回复
            if current_depth < max_depth:
                for i, reply in enumerate(replies_to_process):
                    print(f"\n处理第 {i + 1}/{len(replies_to_process)} 条回复 | URL: {reply['url']}")
                    reply = self.fetch_replies(
                        reply,
                        max_depth,
                        current_depth + 1,
                        max_replies_per_level
                    )
                    
                    if (i + 1) % 15 == 0:
                        sleep_time = random.uniform(3, )
                        print(f"处理 {i + 1} 条后暂停 {sleep_time:.1f} 秒...")
                        time.sleep(sleep_time)
            
            tweet["replies"] = replies
            print(f"\n=== 完成获取回复 (深度 {current_depth}/{max_depth}) ===")
            return tweet

        except Exception as e:
            if "rate limit" in str(e).lower():
                if not handle_rate_limit(self.driver):
                    raise Exception("无法解除限流，请更换IP或稍后再试")
                return self.fetch_replies(tweet, max_depth, current_depth, max_replies_per_level)
            
            print(f"\n!!! 获取回复失败 (深度 {current_depth}/{max_depth}) !!!")
            print(f"错误: {str(e)[:200]}...")
            tweet["replies"] = []
            return tweet
    
    def _extract_replies_from_page(self, current_depth):
        """从当前页面提取回复"""
        replies = []
        seen_in_this_page = set()
        
        # 根据当前深度决定要忽略的元素数量
        
        ignore_count = current_depth
        
        for scroll_attempt in range(20):
            self.limiter.check_limit()
            
            cards = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            valid_cards = cards[ignore_count:] if len(cards) > ignore_count else []
            
            print(f"滚动 {scroll_attempt}: 找到 {len(valid_cards)} 个有效推文卡片 (忽略前{ignore_count}个)")
            
            new_replies = []
            for card in valid_cards:
                tweet_data = self._extract_tweet_data(card)
                if not tweet_data:
                    continue
                    
                tweet_id = tweet_data['id']
                if tweet_id in self.seen_ids or tweet_id in seen_in_this_page:
                    continue
                    
                new_replies.append(tweet_data)
                seen_in_this_page.add(tweet_id)
            
            if new_replies:
                print(f"发现 {len(new_replies)} 条新回复")
                replies.extend(new_replies)
            else:
                print("没有发现新回复")
                
            # 随机滚动
            scroll_height = random.randint(1500, 2000)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_height});")
            random_delay(0.5, 1.5)
            
            # 如果连续3次滚动没有新内容，停止
            if scroll_attempt >= 2 and len(new_replies) == 0:
                break
                
        return replies
    
    def _check_for_more_replies(self, current_depth):
        """检查是否有'查看更多回复'的按钮"""
        more_replies = []
        try:
            more_buttons = self.driver.find_elements(By.XPATH, "//div[@role='button' and contains(., '查看更多回复')]")
            if more_buttons:
                print(f"发现 {len(more_buttons)} 个'查看更多回复'按钮")
                for btn in more_buttons[:2]:  # 最多点击前两个
                    try:
                        self.limiter.check_limit()
                        btn.click()
                        random_delay(2, 3)
                        more_replies = self._extract_replies_from_page(current_depth)
                        print(f"从'查看更多回复'中获取了 {len(more_replies)} 条回复")
                    except Exception as e:
                        print(f"点击'查看更多回复'失败: {str(e)[:100]}...")
                        continue
        except Exception as e:
            print(f"查找'查看更多回复'按钮失败: {str(e)[:100]}...")
            
        return more_replies
    
    def _extract_tweet_data(self, card):
        """从卡片中提取推文数据"""
        try:
            username_elem = card.find_element(By.XPATH, ".//div[@data-testid='User-Name']//a")
            username = username_elem.get_attribute("href").split("/")[-1]
            
            content_elem = card.find_elements(By.XPATH, ".//div[@data-testid='tweetText']")
            content = content_elem[0].text if content_elem else ""
            
            time_elem = card.find_elements(By.TAG_NAME, "time")
            if not time_elem:
                return None
                
            timestamp = time_elem[0].get_attribute("datetime")
            
            links = card.find_elements(By.XPATH, ".//a[contains(@href, '/status/')]")
            status_id = None
            for link in links:
                href = link.get_attribute("href")
                match = re.search(r'/status/(\d+)', href)
                if match:
                    status_id = match.group(1)
                    break
            
            if not status_id:
                return None
                
            return {
                "id": status_id,
                "username": username,
                "timestamp": timestamp,
                "date": str(datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.000Z").date()),
                "content": content,
                "url": f"https://x.com/{username}/status/{status_id}",
                "replies": []
            }
        except Exception as e:
            print(f"提取推文数据出错: {str(e)[:100]}...")
            return None

if __name__ == "__main__":
    os.makedirs("/tmp/chrome-tmp", exist_ok=True)
    
    tag_to_search = "dog"
    max_scrolls = 5
    start_date = datetime.strptime("2025-05-01", "%Y-%m-%d").date()
    end_date = datetime.strptime("2025-06-01", "%Y-%m-%d").date()
    
    driver = create_stealth_driver()
    limiter = RequestLimiter()

    try:
        filtered_tweets = main_scraper(
            tag=tag_to_search,
            max_scrolls=max_scrolls,
            driver=driver,
            start_date=start_date,
            end_date=end_date,
            limiter=limiter
        )
        
        print(f"主爬取完成，找到 {len(filtered_tweets)} 条符合日期范围的推文")
        
        scraper = ReplyScraper(driver, limiter)
        tweets_with_replies = []
        
        for i, tweet in enumerate(filtered_tweets):
            full_tweet = scraper.fetch_replies(tweet)
            tweets_with_replies.append(full_tweet)
            print(f"进度: {i+1}/{len(filtered_tweets)}")
            
            if (i + 1) % 10 == 0:
                sleep_time = random.uniform(10, 30)
                print(f"批量处理暂停 {sleep_time:.1f} 秒...")
                time.sleep(sleep_time)
                
            # 每处理10个主推文更换User-Agent
            if (i + 1) % 10 == 0:
                driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                    "userAgent": get_random_useragent()
                })

        output_file = f"tweets_{tag_to_search}_{start_date}_{end_date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tweets_with_replies, f, ensure_ascii=False, indent=2)

        print(f"爬取完成! 结果已保存到 {output_file}")
        
    finally:
        driver.quit()