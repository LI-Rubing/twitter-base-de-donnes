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

# Chrome user data directory
BASE_USER_DATA_DIR = "/home/user/.config/google-chrome/Default"

class RequestLimiter:
    def __init__(self):
        self.last_request_time = 0
        self.request_count = 0
        self.reset_time = time.time() + 3600  # Reset counter every hour
        
    def check_limit(self):
        current = time.time()
        # No more than 60 requests per minute
        if self.request_count > 60 and current < self.last_request_time + 60:
            wait = (self.last_request_time + 20) - current
            print(f"⚠️ Too many requests, waiting {wait:.1f} seconds")
            time.sleep(wait + random.uniform(1, 3))
            self.request_count = 0
        
        # Reset counter hourly
        if current > self.reset_time:
            self.reset_time = current + 3600
            self.request_count = 0
            
        self.last_request_time = current
        self.request_count += 1

def random_delay(min_sec=1.5, max_sec=5.0):
    """Random delay between actions"""
    delay = random.uniform(min_sec, max_sec)
    if random.random() < 0.02:  # 2% chance for longer delay
        delay += random.uniform(7, 10)
    time.sleep(delay)

def get_random_useragent():
    """Generate random User-Agent"""
    ua = UserAgent()
    return ua.chrome

def create_stealth_driver():
    # Clean up temporary files
    os.system("rm -rf /tmp/chrome-tmp")  # Clear cache
    
    retries = 3
    for attempt in range(retries):
        try:
            options = uc.ChromeOptions()
            
            # Basic configuration
            options.add_argument("--start-maximized")
            options.add_argument("--disk-cache-dir=/tmp/chrome-tmp")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # Get Chrome version
            try:
                chrome_version = subprocess.getoutput("/usr/bin/google-chrome --version").split()[2].split('.')[0]
            except:
                chrome_version = 137  # Default version

            print("Attempting to launch Chrome browser...")
            
            # Minimal initialization
            driver = uc.Chrome(
                options=options,
                browser_executable_path="/usr/bin/google-chrome",
                version_main=int(chrome_version),
            )
            print("Chrome launched successfully")
            # Verify connection
            driver.get("about:blank")
            time.sleep(1)
            return driver
            
        except Exception as e:
            print(f"Initialization failed (attempt {attempt + 1}/{retries}): {str(e)[:200]}")
            os.system("pkill -f chrome")
            time.sleep(2)
            continue

    raise RuntimeError("Failed to initialize Chrome driver, please check browser installation")

def handle_rate_limit(driver):
    """Handle rate limiting"""
    wait_times = [300, 600, 1800]  # 5min, 10min, 30min
    for wait in wait_times:
        print(f"🚨 Possible rate limit detected, waiting {wait//60} minutes...")
        time.sleep(wait)
        
        try:
            driver.get("https://x.com/about")
            if "About" in driver.title:
                print("✅ Rate limit resolved, continuing")
                return True
        except:
            continue
            
    return False

def is_within_date_range(tweet_date, start_date, end_date):
    """Check if tweet date is within specified range"""
    return start_date <= tweet_date <= end_date

def extract_tweet_id(url):
    """Extract tweet ID from URL"""
    match = re.search(r'/status/(\d+)', url)
    return match.group(1) if match else None

def main_scraper(tag, max_scrolls, driver, start_date, end_date, limiter):
    print(f"Starting scrape for #{tag} tweets, date range: {start_date} to {end_date}...")
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
                print(f"Page load failed, retrying ({attempt + 1}): {str(e)[:100]}...")
                random_delay(3, 8)
                driver.refresh()
            else:
                print("Page load failed, skipping")
                return []

    seen = set()
    all_tweets = []
    filtered_tweets = []
    last_count = 0
    stable_scrolls = 0

    for scroll_idx in range(max_scrolls):
        limiter.check_limit()
        
        # Random scroll behavior
        scroll_height = random.randint(1500, 2000)
        driver.execute_script(f"window.scrollBy(0, {scroll_height});")
        random_delay(0.4, 1.2)

        tweet_cards = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
        if not tweet_cards:
            print("No more tweets found, stopping scroll")
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
                    print(f"Error extracting content: {str(e)[:100]}...")

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
                print(f"Error processing tweet: {str(e)[:100]}...")
                continue

        print(f"Scroll {scroll_idx + 1}/{max_scrolls}, total tweets: {len(all_tweets)}, matching date range: {len(filtered_tweets)}")

        if len(all_tweets) == last_count:
            stable_scrolls += 1
            if stable_scrolls >= 3:  # Stop if no new content for 3 scrolls
                print("No new content for 3 consecutive scrolls, stopping")
                break
        else:
            stable_scrolls = 0
        last_count = len(all_tweets)

        # Random reading behavior
        if random.random() < 0.2:
            read_time = random.uniform(3, 4)
            print(f"Simulating reading behavior, pausing {read_time:.1f} seconds...")
            time.sleep(read_time)

    return filtered_tweets

class ReplyScraper:
    def __init__(self, driver, limiter):
        self.driver = driver
        self.limiter = limiter
        self.seen_ids = set()  # Global record of processed tweet IDs
        self.max_depth = 0
        self.current_depth = 0
    
    def fetch_replies(self, tweet, max_depth=2, current_depth=1, max_replies_per_level=5):
        if current_depth > max_depth:
            return tweet
            
        try:
            self.limiter.check_limit()
            print(f"\n=== Fetching replies (depth {current_depth}/{max_depth}) ===")
            print(f"Parent tweet URL: {tweet['url']}")
            
            tweet_id = tweet.get('id') or extract_tweet_id(tweet['url'])
            if not tweet_id:
                print("Cannot get tweet ID, skipping")
                return tweet
                
            if tweet_id in self.seen_ids:
                print(f"Tweet {tweet_id} already processed, skipping")
                return tweet
                
            self.seen_ids.add(tweet_id)
            
            # Change User-Agent dynamically
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": get_random_useragent()
            })
            
            self.driver.get(tweet["url"])
            WebDriverWait(self.driver, random.randint(15, 25)).until(
                EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
            )
            random_delay()

            # Get all replies on current page
            replies = self._extract_replies_from_page(current_depth)
            print(f"Initially extracted {len(replies)} replies (depth {current_depth})")
            
            # Handle "Show more replies" for first level
            if current_depth == 0 and len(replies) < 3:
                replies.extend(self._check_for_more_replies(current_depth))
                print(f"After checking more replies, total: {len(replies)}")
            
            # Limit replies per level
            if len(replies) > max_replies_per_level:
                print(f"Filtering top {max_replies_per_level} from {len(replies)} replies for deep scraping")
                replies_to_process = replies[:max_replies_per_level]
            else:
                replies_to_process = replies
                
            # Recursively fetch deeper replies
            if current_depth < max_depth:
                for i, reply in enumerate(replies_to_process):
                    print(f"\nProcessing reply {i + 1}/{len(replies_to_process)} | URL: {reply['url']}")
                    reply = self.fetch_replies(
                        reply,
                        max_depth,
                        current_depth + 1,
                        max_replies_per_level
                    )
                    
                    if (i + 1) % 15 == 0:
                        sleep_time = random.uniform(3, 5)
                        print(f"Pausing {sleep_time:.1f} seconds after {i + 1} replies...")
                        time.sleep(sleep_time)
            
            tweet["replies"] = replies
            print(f"\n=== Completed fetching replies (depth {current_depth}/{max_depth}) ===")
            return tweet

        except Exception as e:
            if "rate limit" in str(e).lower():
                if not handle_rate_limit(self.driver):
                    raise Exception("Cannot resolve rate limit, please change IP or try later")
                return self.fetch_replies(tweet, max_depth, current_depth, max_replies_per_level)
            
            print(f"\n!!! Failed to fetch replies (depth {current_depth}/{max_depth}) !!!")
            print(f"Error: {str(e)[:200]}...")
            tweet["replies"] = []
            return tweet
    
    def _extract_replies_from_page(self, current_depth):
        """Extract replies from current page"""
        replies = []
        seen_in_this_page = set()
        
        # Number of elements to ignore based on depth
        ignore_count = current_depth
        
        for scroll_attempt in range(20):
            self.limiter.check_limit()
            
            cards = self.driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
            valid_cards = cards[ignore_count:] if len(cards) > ignore_count else []
            
            print(f"Scroll {scroll_attempt}: found {len(valid_cards)} valid tweet cards (ignoring first {ignore_count})")
            
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
                print(f"Found {len(new_replies)} new replies")
                replies.extend(new_replies)
            else:
                print("No new replies found")
                
            # Random scroll
            scroll_height = random.randint(1500, 2000)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_height});")
            random_delay(0.5, 1.5)
            
            # Stop if no new content for 3 scrolls
            if scroll_attempt >= 2 and len(new_replies) == 0:
                break
                
        return replies
    
    def _check_for_more_replies(self, current_depth):
        """Check for 'Show more replies' buttons"""
        more_replies = []
        try:
            more_buttons = self.driver.find_elements(By.XPATH, "//div[@role='button' and contains(., 'Show more replies')]")
            if more_buttons:
                print(f"Found {len(more_buttons)} 'Show more replies' buttons")
                for btn in more_buttons[:2]:  # Max click first two
                    try:
                        self.limiter.check_limit()
                        btn.click()
                        random_delay(2, 3)
                        more_replies = self._extract_replies_from_page(current_depth)
                        print(f"Extracted {len(more_replies)} replies from 'Show more replies'")
                    except Exception as e:
                        print(f"Clicking 'Show more replies' failed: {str(e)[:100]}...")
                        continue
        except Exception as e:
            print(f"Failed to find 'Show more replies' buttons: {str(e)[:100]}...")
            
        return more_replies
    
    def _extract_tweet_data(self, card):
        """Extract tweet data from card"""
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
            print(f"Error extracting tweet data: {str(e)[:100]}...")
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
        
        print(f"Main scrape completed, found {len(filtered_tweets)} tweets matching date range")
        
        scraper = ReplyScraper(driver, limiter)
        tweets_with_replies = []
        
        for i, tweet in enumerate(filtered_tweets):
            full_tweet = scraper.fetch_replies(tweet)
            tweets_with_replies.append(full_tweet)
            print(f"Progress: {i+1}/{len(filtered_tweets)}")
            
            if (i + 1) % 10 == 0:
                sleep_time = random.uniform(10, 30)
                print(f"Batch processing pause for {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                
            # Change User-Agent every 10 parent tweets
            if (i + 1) % 10 == 0:
                driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                    "userAgent": get_random_useragent()
                })

        output_file = f"tweets_{tag_to_search}_{start_date}_{end_date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(tweets_with_replies, f, ensure_ascii=False, indent=2)

        print(f"Scraping completed! Results saved to {output_file}")
        
    finally:
        driver.quit()