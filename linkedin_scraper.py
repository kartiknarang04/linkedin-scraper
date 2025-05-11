import os
import sys
import time
import random
import re
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import json
import requests
from uuid import uuid4

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInScraper:
    def setup_driver(self,headless=True):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
    
        driver_path = ChromeDriverManager().install()
        os.chmod(driver_path, 0o755)  # ensure it's executable
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def __init__(self, headless=False, debug=True, max_posts=5):
        """Initialize the LinkedIn scraper with login credentials."""
        self.email = os.getenv("LINKEDIN_EMAIL")
        self.password = os.getenv("LINKEDIN_PASSWORD")
        self.debug = debug
        self.max_posts = max_posts
        self.session_id = str(uuid4())[:8]  # Generate a unique session ID
        
        # Create debug directory
        if self.debug:
            os.makedirs('debug', exist_ok=True)
        
        # Create data directory
        os.makedirs('data', exist_ok=True)
        
        # Setup Selenium options
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-notifications')
        options.add_argument('--window-size=1920,1080')
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Initialize the driver
        self.driver =self.setup_driver(headless=headless)
        self.wait = WebDriverWait(self.driver, 15)
        self.logged_in = False
        
        # Take screenshot on initialization to verify browser is working
        if self.debug:
            self.driver.get("https://www.google.com")
            time.sleep(2)
            self.driver.save_screenshot(f'debug/{self.session_id}_browser_init.png')
    
    def login(self):
        """Log in to LinkedIn."""
        try:
            logger.info("Navigating to LinkedIn login page")
            self.driver.get('https://www.linkedin.com/login')
            time.sleep(3)
            
            # Take screenshot of login page
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_login_page.png')
            
            # Wait for login page to load
            self.wait.until(EC.presence_of_element_located((By.ID, 'username')))
            
            # Enter email
            username_field = self.driver.find_element(By.ID, 'username')
            username_field.clear()
            username_field.send_keys(self.email)
            
            # Enter password
            password_field = self.driver.find_element(By.ID, 'password')
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Click the login button
            self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
            
            # Wait for the homepage to load
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, 'global-nav')))
                logger.info("Successfully logged in")
                self.logged_in = True
                
                # Take screenshot after login
                if self.debug:
                    self.driver.save_screenshot(f'debug/{self.session_id}_after_login.png')
                
                # Wait a bit after login
                time.sleep(5)
                
            except TimeoutException:
                # Check if we got a security verification page
                if "security verification" in self.driver.page_source.lower() or "challenge" in self.driver.page_source.lower():
                    logger.warning("Security verification detected. Please complete it manually.")
                    if self.debug:
                        self.driver.save_screenshot(f'debug/{self.session_id}_security_verification.png')
                    input("Complete the security verification and press Enter to continue...")
                    self.logged_in = True
                else:
                    logger.error("Login failed - couldn't detect navigation bar")
                    if self.debug:
                        self.driver.save_screenshot(f'debug/{self.session_id}_login_failure.png')
        
        except Exception as e:
            logger.error(f"Failed to login: {str(e)}")
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_login_error.png')
            raise e
    
    def navigate_to_profile(self, profile_url):
        """Navigate to a LinkedIn profile and ensure it's loaded."""
        if not self.logged_in:
            self.login()
        
        try:
            # Ensure URL is the recent-activity/all page
            if "recent-activity/all" not in profile_url:
                if not profile_url.endswith('/'):
                    profile_url = profile_url + '/'
                profile_url = profile_url + "recent-activity/all/"
            
            logger.info(f"Navigating to activity page: {profile_url}")
            self.driver.get(profile_url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Take screenshot of profile page
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_profile_page.png')
            
            # Check if we're on the right page
            if "recent-activity" not in self.driver.current_url:
                logger.warning(f"Not on activity page. Current URL: {self.driver.current_url}")
                if self.debug:
                    self.driver.save_screenshot(f'debug/{self.session_id}_wrong_page.png')
                return False
            
            # Wait for content to load
            try:
                # Wait for any of these elements that indicate posts are loaded
                selectors = [
                    ".occludable-update",
                    ".feed-shared-update-v2",
                    ".profile-creator-shared-feed-update__container"
                ]
                
                for selector in selectors:
                    try:
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        logger.info(f"Found posts with selector: {selector}")
                        return True
                    except:
                        continue
                
                logger.warning("Could not find any post elements")
                if self.debug:
                    self.driver.save_screenshot(f'debug/{self.session_id}_no_posts_found.png')
                return False
                
            except TimeoutException:
                logger.warning("Timeout waiting for posts to load")
                if self.debug:
                    self.driver.save_screenshot(f'debug/{self.session_id}_posts_timeout.png')
                return False
                
        except Exception as e:
            logger.error(f"Error navigating to profile: {str(e)}")
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_navigation_error.png')
            return False
    
    def scroll_to_top(self):
        """Scroll to the top of the page."""
        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            logger.info("Scrolled to top of page")
            return True
        except Exception as e:
            logger.error(f"Error scrolling to top: {str(e)}")
            return False
    
    def scroll_and_expand_posts(self, max_scrolls=5):
        """Scroll the page to load posts and expand 'see more' links."""
        try:
            # First scroll to top
            self.scroll_to_top()
            
            # Take screenshot before scrolling
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_before_scrolling.png')
            
            # Scroll down gradually to load posts
            for i in range(max_scrolls):
                logger.info(f"Scroll {i+1}/{max_scrolls}")
                
                # Find all "see more" links and expand them
                self.expand_all_see_more()
                
                # Scroll down
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(2)
                
                # Every 3 scrolls, take a screenshot
                if self.debug and i % 3 == 0:
                    self.driver.save_screenshot(f'debug/{self.session_id}_scrolling_{i+1}.png')
            
            # Final expansion of "see more" links
            self.expand_all_see_more()
            
            # Take screenshot after scrolling
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_after_scrolling.png')
            
            return True
            
        except Exception as e:
            logger.error(f"Error during scrolling: {str(e)}")
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_scrolling_error.png')
            return False
    
    def expand_all_see_more(self):
        """Find and click all 'see more' links on the page."""
        try:
            # Find all elements that might be "see more" buttons
            see_more_selectors = [
                ".inline-show-more-text__button",
                ".feed-shared-inline-show-more-text__see-more",
                ".feed-shared-text-view__see-more",
                ".see-more",
                "span.lt-line-clamp__more"
            ]
            
            for selector in see_more_selectors:
                try:
                    see_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"Found {len(see_more_buttons)} potential 'see more' buttons with selector: {selector}")
                    
                    for button in see_more_buttons:
                        try:
                            if button.is_displayed():
                                # Try to scroll to the button
                                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                                time.sleep(1)
                                
                                # Try JavaScript click
                                try:
                                    self.driver.execute_script("arguments[0].click();", button)
                                    logger.info("Expanded post with JS click")
                                    time.sleep(1)
                                except:
                                    # Try regular click
                                    try:
                                        button.click()
                                        logger.info("Expanded post with regular click")
                                        time.sleep(1)
                                    except:
                                        pass
                        except:
                            continue
                except:
                    continue
            
            # Also try a more aggressive approach with JavaScript
            try:
                expanded_count = self.driver.execute_script("""
                    const expandButtons = [];
                    
                    // Find all elements containing "...more" or "see more" text
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent;
                        if ((text.includes('…more') || 
                             text.includes('...more') || 
                             text.toLowerCase().includes('see more')) && 
                            el.offsetWidth > 0 && 
                            el.offsetHeight > 0) {
                            
                            try {
                                el.click();
                                expandButtons.push(el);
                            } catch (e) {
                                // Try parent element
                                try {
                                    el.parentElement.click();
                                    expandButtons.push(el.parentElement);
                                } catch (e2) {
                                    // Ignore
                                }
                            }
                        }
                    }
                    
                    return expandButtons.length;
                """)
                
                if expanded_count > 0:
                    logger.info(f"Expanded {expanded_count} 'see more' buttons with JavaScript")
                    time.sleep(2)
            except:
                pass
                
            return True
            
        except Exception as e:
            logger.error(f"Error expanding 'see more' links: {str(e)}")
            return False
    
    def is_element_in_viewport(self, element):
        """Check if an element is visible in the current viewport."""
        try:
            return self.driver.execute_script("""
                var elem = arguments[0];
                var rect = elem.getBoundingClientRect();
                return (
                    rect.top >= 0 &&
                    rect.left >= 0 &&
                    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
                );
            """, element)
        except:
            return False
    
    def extract_posts(self):
        """Extract all original posts from the current page."""
        try:
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_before_extraction.png')
            
            # First, scroll to top to ensure we start from the top (most recent posts)
            self.scroll_to_top()
            time.sleep(3)  # Give page time to load top content
            
            # Find all post containers at the top of the page
            post_selectors = [
                ".feed-shared-update-v2",
                ".occludable-update",
                ".profile-creator-shared-feed-update__container"
            ]
            
            all_posts = []
            for selector in post_selectors:
                posts = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if posts:
                    logger.info(f"Found {len(posts)} posts with selector: {selector}")
                    all_posts = posts[:15]  # Take only the first 15 posts (likely the most recent ones)
                    break
            
            if not all_posts:
                logger.warning("No posts found")
                if self.debug:
                    self.driver.save_screenshot(f'debug/{self.session_id}_no_posts.png')
                return []
            
            # Extract data from each post
            post_data = []
            post_count = 0
            
            for i, post in enumerate(all_posts):
                try:
                    logger.info(f"Processing post {i+1}/{len(all_posts)}")
                    
                    # Scroll to the post to ensure it's in view
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", post)
                        time.sleep(1)
                    except:
                        logger.warning(f"Could not scroll to post {i+1}")
                    
                    # Debug screenshot
                    if self.debug:
                        self.driver.save_screenshot(f'debug/{self.session_id}_post_{i+1}.png')
                    
                    # Check if this is an original post
                    if not self.is_original_post(post):
                        logger.info(f"Post {i+1} is not an original post, skipping")
                        continue
                    
                    # Extract post data
                    post_text = self.extract_post_text(post)
                    post_date = self.extract_post_date(post)
                    
                    # Log the post data being extracted
                    logger.info(f"Post {i+1}: Text length={len(post_text)}, Date={post_date}")
                    
                    # Extract engagement metrics
                    reactions, comments, reposts = self.extract_engagement(post)
                    
                    # Parse the date
                    parsed_date = self.parse_date(post_date)
                    formatted_date = parsed_date.strftime('%Y-%m-%d %H:%M:%S') if parsed_date else "Unknown"
                    day_of_week = parsed_date.strftime('%A') if parsed_date else "Unknown"
                    hour_of_day = parsed_date.strftime('%H') if parsed_date else "Unknown"
                    
                    # Extract hashtags
                    hashtags = re.findall(r'#\w+', post_text)
                    
                    # Get profile name
                    profile_name = self.extract_profile_name()
                    
                    # Add to post data
                    post_data.append({
                        'profile_name': profile_name,
                        'profile_url': self.driver.current_url.split('/recent-activity')[0],
                        'post_text': post_text,
                        'post_date_text': post_date,
                        'post_date': formatted_date,
                        'day_of_week': day_of_week,
                        'hour_of_day': hour_of_day,
                        'reactions': reactions,
                        'comments': comments,
                        'reposts': reposts,
                        'total_engagement': reactions + comments + reposts,
                        'hashtags': ', '.join(hashtags),
                        'hashtag_count': len(hashtags),
                        'post_length': len(post_text),
                        'scraped_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'session_id': self.session_id
                    })
                    
                    logger.info(f"Successfully extracted post {i+1}")
                    
                    # Increment post count and check if we've reached the limit
                    post_count += 1
                    if post_count >= self.max_posts:
                        logger.info(f"Reached limit of {self.max_posts} posts")
                        break
                    
                except Exception as e:
                    logger.error(f"Error processing post {i+1}: {str(e)}")
                    continue
            
            logger.info(f"Extracted {len(post_data)} posts")
            return post_data
            
        except Exception as e:
            logger.error(f"Error extracting posts: {str(e)}")
            if self.debug:
                self.driver.save_screenshot(f'debug/{self.session_id}_extraction_error.png')
            return []
    
    
    def is_original_post(self, post):
        """Check if a post is an original post (not a like, comment, etc.)."""
        try:
            # Check for activity indicators
            activity_texts = [
                "liked", "commented on", "replied", "reposted", 
                "shared", "celebrates", "mentioned in", "follows"
            ]
            
            post_text = post.text.lower()
            
            # If the post contains any activity indicators at the beginning, it's not original
            for activity in activity_texts:
                if post_text.startswith(activity) or f"\n{activity}" in post_text[:50]:
                    return False
            
            # Check for content indicators
            content_selectors = [
                ".feed-shared-update-v2__description",
                ".feed-shared-text",
                ".update-components-text",
                ".feed-shared-text-view",
                ".update-components-update-v2__commentary"
            ]
            
            for selector in content_selectors:
                content_elements = post.find_elements(By.CSS_SELECTOR, selector)
                if content_elements and any(el.text.strip() for el in content_elements):
                    return True
            
            # If we can't determine, assume it's not original
            return False
            
        except Exception as e:
            logger.error(f"Error checking if post is original: {str(e)}")
            return False
    
    def extract_post_text(self, post):
        """Extract the text content of a post."""
        try:
            # Try to expand "see more" links in this post
            self.expand_see_more_in_post(post)
            
            # Try different selectors for post content
            content_selectors = [
                ".feed-shared-update-v2__description",
                ".feed-shared-text",
                ".update-components-text",
                ".feed-shared-text-view"
            ]
            
            post_text = ""
            for selector in content_selectors:
                elements = post.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and len(text) > len(post_text):
                        post_text = text
            
            # If no text found, try JavaScript
            if not post_text:
                post_text = self.driver.execute_script("""
                    const post = arguments[0];
                    
                    // Try to find the main text content
                    const contentElements = post.querySelectorAll('p, span.break-words, div.break-words');
                    let text = '';
                    
                    for (const el of contentElements) {
                        if (el.textContent.trim() && el.offsetWidth > 0 && el.offsetHeight > 0) {
                            text += el.textContent.trim() + '\\n';
                        }
                    }
                    
                    return text.trim();
                """, post)
            
            # Clean up the text
            post_text = re.sub(r'\n\s*\n', '\n\n', post_text)  # Remove extra newlines
            post_text = re.sub(r' +', ' ', post_text)  # Remove extra spaces
            
            return post_text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting post text: {str(e)}")
            return "Error extracting text"
    
    def expand_see_more_in_post(self, post):
        """Expand 'see more' links in a specific post."""
        try:
            # Find all "see more" links in this post
            see_more_selectors = [
                ".inline-show-more-text__button",
                ".feed-shared-inline-show-more-text__see-more",
                ".feed-shared-text-view__see-more",
                ".see-more",
                "span.lt-line-clamp__more"
            ]
            
            for selector in see_more_selectors:
                try:
                    see_more_buttons = post.find_elements(By.CSS_SELECTOR, selector)
                    for button in see_more_buttons:
                        try:
                            if button.is_displayed():
                                # Try JavaScript click
                                self.driver.execute_script("arguments[0].click();", button)
                                time.sleep(1)
                        except:
                            pass
                except:
                    continue
            
            # Also try with JavaScript
            self.driver.execute_script("""
                const post = arguments[0];
                
                // Find all elements containing "...more" or "see more" text
                const allElements = post.querySelectorAll('*');
                for (const el of allElements) {
                    const text = el.textContent;
                    if ((text.includes('…more') || 
                         text.includes('...more') || 
                         text.toLowerCase().includes('see more')) && 
                        el.offsetWidth > 0 && 
                        el.offsetHeight > 0) {
                        
                        try {
                            el.click();
                        } catch (e) {
                            // Try parent element
                            try {
                                el.parentElement.click();
                            } catch (e2) {
                                // Ignore
                            }
                        }
                    }
                }
            """, post)
            
            return True
            
        except Exception as e:
            logger.error(f"Error expanding 'see more' in post: {str(e)}")
            return False
    
    def extract_post_date(self, post):
        """Extract the date of a post."""
        try:
            # Try different selectors for post date
            date_selectors = [
                ".feed-shared-actor__sub-description",
                ".update-components-actor__sub-description",
                "time",
                ".feed-shared-actor__creation-time",
                ".update-components-actor__meta-link",
                ".update-components-text-view time",
                ".artdeco-entity-lockup__caption"
            ]
            
            for selector in date_selectors:
                elements = post.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    date_text = element.text.strip()
                    if date_text and any(indicator in date_text.lower() for indicator in ["ago", "hour", "day", "min", "sec", "just now", "week", "month", "yr"]):
                        return date_text
            
            # If no date found, try JavaScript
            date_text = self.driver.execute_script("""
                const post = arguments[0];
                
                // Try to find time elements
                const timeElements = post.querySelectorAll('time');
                for (const el of timeElements) {
                    if (el.textContent.trim()) {
                        return el.textContent.trim();
                    }
                }
                
                // Try to find elements with date-like text
                const dateIndicators = ["ago", "hour", "day", "min", "sec", "just now", "week", "month", "yr"];
                const allElements = post.querySelectorAll('span, div');
                
                for (const el of allElements) {
                    const text = el.textContent.trim().toLowerCase();
                    if (text && dateIndicators.some(indicator => text.includes(indicator))) {
                        return el.textContent.trim();
                    }
                }
                
                return "Unknown date";
            """, post)
            
            return date_text
            
        except Exception as e:
            logger.error(f"Error extracting post date: {str(e)}")
            return "Unknown date"
    
    def parse_date(self, date_text):
        """Parse a date string into a datetime object."""
        try:
            now = datetime.now()
            
            if not date_text or date_text == "Unknown date":
                return None
                
            # Handle "Just now" or "now"
            if "just now" in date_text.lower() or date_text.lower() == "now":
                return now
                
            # Handle "X minutes/hours/days/weeks/months/years ago"
            ago_match = re.search(r'(\d+)\s*(minute|hour|day|week|month|year)s?\s*ago', date_text.lower())
            if ago_match:
                value = int(ago_match.group(1))
                unit = ago_match.group(2)
                
                if unit == "minute":
                    return now - timedelta(minutes=value)
                elif unit == "hour":
                    return now - timedelta(hours=value)
                elif unit == "day":
                    return now - timedelta(days=value)
                elif unit == "week":
                    return now - timedelta(weeks=value)
                elif unit == "month":
                    return now - timedelta(days=value*30)  # Approximation
                elif unit == "year":
                    return now - timedelta(days=value*365)  # Approximation
            
            # Handle short formats like "2d", "5h", "3w", "1mo", "2yr"
            short_match = re.search(r'(\d+)\s*(s|m|h|d|w|mo|yr)', date_text.lower())
            if short_match:
                value = int(short_match.group(1))
                unit = short_match.group(2)
                
                if unit == "s":
                    return now - timedelta(seconds=value)
                elif unit == "m":
                    return now - timedelta(minutes=value)
                elif unit == "h":
                    return now - timedelta(hours=value)
                elif unit == "d":
                    return now - timedelta(days=value)
                elif unit == "w":
                    return now - timedelta(weeks=value)
                elif unit == "mo":
                    return now - timedelta(days=value*30)  # Approximation
                elif unit == "yr":
                    return now - timedelta(days=value*365)  # Approximation
            
            # Try to parse actual date formats
            try:
                return datetime.strptime(date_text, "%b %d, %Y")
            except:
                pass
                
            try:
                return datetime.strptime(date_text, "%B %d, %Y")
            except:
                pass
                
            # If all else fails, return None
            return None
            
        except Exception as e:
            logger.error(f"Error parsing date: {str(e)}")
            return None
    
    def extract_engagement(self, post):
        """Extract engagement metrics (reactions, comments, reposts) from a post."""
        try:
            reactions = 0
            comments = 0
            reposts = 0
            
            # Try to find social counts container
            social_counts_selectors = [
                ".social-details-social-counts",
                ".update-components-social-activity",
                ".social-action-counts"
            ]
            
            # First try to find the social counts container
            social_container = None
            for selector in social_counts_selectors:
                containers = post.find_elements(By.CSS_SELECTOR, selector)
                if containers:
                    social_container = containers[0]
                    break
            
            if social_container:
                # Extract from container using JavaScript for more reliable extraction
                engagement_data = self.driver.execute_script("""
                    const container = arguments[0];
                    const text = container.textContent.toLowerCase();
                    
                    let reactions = 0;
                    let comments = 0;
                    let reposts = 0;
                    
                    // Look for reactions
                    const reactionsMatch = text.match(/(\\d+[\\d,.km]*)[\\s]*(?:like|reaction)/i);
                    if (reactionsMatch) {
                        const numStr = reactionsMatch[1].replace(/[^\\d.km]/gi, '');
                        if (numStr.includes('k')) reactions = parseFloat(numStr) * 1000;
                        else if (numStr.includes('m')) reactions = parseFloat(numStr) * 1000000;
                        else reactions = parseInt(numStr);
                    }
                    
                    // Look for comments
                    const commentsMatch = text.match(/(\\d+[\\d,.km]*)[\\s]*comment/i);
                    if (commentsMatch) {
                        const numStr = commentsMatch[1].replace(/[^\\d.km]/gi, '');
                        if (numStr.includes('k')) comments = parseFloat(numStr) * 1000;
                        else if (numStr.includes('m')) comments = parseFloat(numStr) * 1000000;
                        else comments = parseInt(numStr);
                    }
                    
                    // Look for reposts
                    const repostsMatch = text.match(/(\\d+[\\d,.km]*)[\\s]*(?:repost|share)/i);
                    if (repostsMatch) {
                        const numStr = repostsMatch[1].replace(/[^\\d.km]/gi, '');
                        if (numStr.includes('k')) reposts = parseFloat(numStr) * 1000;
                        else if (numStr.includes('m')) reposts = parseFloat(numStr) * 1000000;
                        else reposts = parseInt(numStr);
                    }
                    
                    return { reactions, comments, reposts };
                """, social_container)
                
                reactions = engagement_data['reactions']
                comments = engagement_data['comments']
                reposts = engagement_data['reposts']
            
            # If no metrics found, try alternative approach
            if reactions == 0 and comments == 0 and reposts == 0:
                # Try to find reaction count
                reaction_selectors = [
                    ".social-details-social-counts__reactions-count",
                    ".social-details-social-counts__social-proof-text",
                    ".social-action-counts__count"
                ]
                
                for selector in reaction_selectors:
                    elements = post.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and ("like" in text.lower() or "reaction" in text.lower() or text.isdigit() or "k" in text.lower()):
                            count = self.parse_count(text)
                            if count > reactions:
                                reactions = count
                
                # Try to find comment count
                comment_selectors = [
                    ".social-details-social-counts__comments",
                    ".comments-comment-box__comment-count",
                    ".social-action-counts__comments"
                ]
                
                for selector in comment_selectors:
                    elements = post.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and ("comment" in text.lower() or text.isdigit() or "k" in text.lower()):
                            count = self.parse_count(text)
                            if count > comments:
                                comments = count
                
                # Try to find repost count
                repost_selectors = [
                    ".social-details-social-counts__reshares",
                    ".social-action-counts__reshares"
                ]
                
                for selector in repost_selectors:
                    elements = post.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and ("repost" in text.lower() or "share" in text.lower() or text.isdigit() or "k" in text.lower()):
                            count = self.parse_count(text)
                            if count > reposts:
                                reposts = count
            
            # If still no metrics found, try JavaScript
            if reactions == 0 and comments == 0 and reposts == 0:
                metrics = self.driver.execute_script("""
                    const post = arguments[0];
                    let reactions = 0;
                    let comments = 0;
                    let reposts = 0;
                    
                    // Look for elements with engagement metrics
                    const allElements = post.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent.trim().toLowerCase();
                        
                        // Check for reactions
                        if (text.includes('like') || text.includes('reaction')) {
                            const match = text.match(/\\d+[\\d,.km]*\\s*(like|reaction)/i);
                            if (match) {
                                let num = match[0].replace(/[^\\d.km]/gi, '');
                                if (num.includes('k')) reactions = parseFloat(num) * 1000;
                                else if (num.includes('m')) reactions = parseFloat(num) * 1000000;
                                else reactions = parseInt(num);
                            }
                        }
                        
                        // Check for comments
                        if (text.includes('comment')) {
                            const match = text.match(/\\d+[\\d,.km]*\\s*comment/i);
                            if (match) {
                                let num = match[0].replace(/[^\\d.km]/gi, '');
                                if (num.includes('k')) comments = parseFloat(num) * 1000;
                                else if (num.includes('m')) comments = parseFloat(num) * 1000000;
                                else comments = parseInt(num);
                            }
                        }
                        
                        // Check for reposts
                        if (text.includes('repost') || text.includes('share')) {
                            const match = text.match(/\\d+[\\d,.km]*\\s*(repost|share)/i);
                            if (match) {
                                let num = match[0].replace(/[^\\d.km]/gi, '');
                                if (num.includes('k')) reposts = parseFloat(num) * 1000;
                                else if (num.includes('m')) reposts = parseFloat(num) * 1000000;
                                else reposts = parseInt(num);
                            }
                        }
                    }
                    
                    return { reactions, comments, reposts };
                """, post)
                
                reactions = metrics['reactions']
                comments = metrics['comments']
                reposts = metrics['reposts']
            
            return reactions, comments, reposts
            
        except Exception as e:
            logger.error(f"Error extracting engagement: {str(e)}")
            return 0, 0, 0
    
    def parse_count(self, text):
        """Parse a count from text like '25 comments' or '1.2K reactions'."""
        try:
            if not text:
                return 0
                
            # Extract numbers
            number_match = re.search(r'(\d+,?\d*)|(\d*\.?\d+[KkMm])', text)
            if not number_match:
                return 0
                
            count_str = number_match.group(0).strip().replace(',', '')
            
            # Handle K/M suffixes
            if 'k' in count_str.lower():
                return int(float(count_str.lower().replace('k', '')) * 1000)
            elif 'm' in count_str.lower():
                return int(float(count_str.lower().replace('m', '')) * 1000000)
            else:
                try:
                    return int(float(count_str))
                except:
                    return 0
                    
        except Exception as e:
            logger.error(f"Error parsing count: {str(e)}")
            return 0
    
    def extract_profile_name(self):
        """Extract the profile name from the current page."""
        try:
            # Try to find the profile name
            profile_name = self.driver.execute_script("""
                // Try to find profile name
                const nameElement = document.querySelector('h1.text-heading-xlarge') || 
                                   document.querySelector('.pv-text-details__left-panel h1');
                return nameElement ? nameElement.textContent.trim() : null;
            """)
            
            if not profile_name:
                # Try to extract from URL
                current_url = self.driver.current_url
                if '/in/' in current_url:
                    profile_name = current_url.split('/in/')[1].split('/')[0].replace('-', ' ').title()
                else:
                    profile_name = "Unknown Profile"
            
            return profile_name
            
        except Exception as e:
            logger.error(f"Error extracting profile name: {str(e)}")
            return "Unknown Profile"
    
    def scrape_profile(self, profile_url):
        """Scrape a LinkedIn profile for original posts."""
        try:
            # Navigate to the profile
            if not self.navigate_to_profile(profile_url):
                logger.error(f"Failed to navigate to profile: {profile_url}")
                return []
            
            # Scroll and expand posts
            if not self.scroll_and_expand_posts():
                logger.warning(f"Issues during scrolling for profile: {profile_url}")
            
            # Extract posts
            posts = self.extract_posts()
            
            return posts
            
        except Exception as e:
            logger.error(f"Error scraping profile {profile_url}: {str(e)}")
            return []
    
    def scrape_multiple_profiles(self, profile_urls):
        """Scrape multiple LinkedIn profiles for original posts."""
        all_posts = []
        
        for url in profile_urls:
            try:
                logger.info(f"Starting to scrape profile: {url}")
                profile_posts = self.scrape_profile(url)
                
                if profile_posts:
                    logger.info(f"Scraped {len(profile_posts)} posts from {url}")
                    all_posts.extend(profile_posts)
                else:
                    logger.warning(f"No posts scraped from {url}")
                
                # Add a delay between profiles
                delay = random.uniform(10, 15)
                logger.info(f"Waiting {delay:.1f} seconds before next profile...")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Failed to scrape profile {url}: {str(e)}")
        
        # Save to CSV - APPEND instead of overwrite
        if all_posts:
            df_new = pd.DataFrame(all_posts)
            output_file = 'data/linkedin_original_posts.csv'
            
            # Save the current session data to a separate file
            session_file = f'data/linkedin_posts_{self.session_id}.csv'
            df_new.to_csv(session_file, index=False)
            logger.info(f"Saved {len(df_new)} posts from this session to {session_file}")
            
            # Check if main file exists and append if it does
            if os.path.exists(output_file):
                df_existing = pd.read_csv(output_file)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                # Remove duplicates based on post_text and profile_name
                df_combined = df_combined.drop_duplicates(subset=['post_text', 'profile_name'], keep='first')
                df_combined.to_csv(output_file, index=False)
                logger.info(f"Appended {len(df_new)} new posts to existing file. Total: {len(df_combined)} posts")
                return df_new, df_combined  # Return both new data and combined data
            else:
                df_new.to_csv(output_file, index=False)
                logger.info(f"Saved {len(df_new)} original posts to new file {output_file}")
                return df_new, df_new  # Return new data as both
        else:
            logger.warning("No original posts were scraped")
            return pd.DataFrame(), pd.DataFrame()
    
    def close(self):
        """Close the browser."""
        self.driver.quit()
        logger.info("Browser closed")
