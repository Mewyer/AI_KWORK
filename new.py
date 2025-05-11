from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import time
import urllib.parse
import sys
import os
import json
from PIL import Image

def login(driver, email, password):
    try:
        print("Opening login page...")
        driver.get("https://videohunt.ai/login")
        time.sleep(2)

        print("Checking for input fields...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "input.vh-input")))
        
        print("Entering email...")
        email_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "basic_email_login"))
        )
        email_field.clear()
        email_field.send_keys(email)
        
        print("Entering password...")
        password_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.vh-input[type='password']"))
        )
        password_field.clear()
        password_field.send_keys(password)
        
        print("Clicking login button...")
        login_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'].vh-btn-primary"))
        )
        login_button.click()
        time.sleep(30)
        
        print("Successfully logged in!")
        return True
        
    except TimeoutException:
        print("Timeout waiting for elements. Check your internet connection.")
        return False
    except NoSuchElementException:
        print("Required elements not found. The site structure may have changed.")
        return False
    except WebDriverException as e:
        print(f"WebDriver error: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected login error: {str(e)}")
        return False

def take_element_screenshot(driver, element, file_path):
    """Take screenshot of a specific element"""
    try:
        # Scroll to the element first
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(1)
        
        # Take screenshot using Selenium's built-in method
        element.screenshot(file_path)
        return file_path
    except Exception as e:
        print(f"Error taking element screenshot: {str(e)}")
        return None

def process_video(driver, video_url, prompt, screenshot_path):
    try:
        encoded_url = urllib.parse.quote(video_url)
        target_url = f"https://videohunt.ai/video/result?url={encoded_url}&input_t=URL"
        print(f"Navigating to video page: {target_url}")
        driver.get(target_url)
        time.sleep(10)

        print("Entering prompt...")
        input_field = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.vh-input.placeholder\\:italic.ml-6.bg-red-500"))
        )
        input_field.clear()
        input_field.send_keys(prompt)
        
        print("Clicking Find button...")
        find_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.search-button"))
        )
        find_button.click()
        time.sleep(120)

        print("Waiting for results to load...")
        time.sleep(120)
        WebDriverWait(driver, 300).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.w-full.relative"))
        )
        
        # Find all elements with the specified class
        elements = driver.find_elements(By.CSS_SELECTOR, "div.flex-1.min-w-0.flex.flex-col")
        print(f"Found {len(elements)} elements for screenshots")
        
        # Create screenshots directory
        screenshots_dir = os.path.join(os.path.dirname(screenshot_path), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Take screenshots of each element
        element_screenshots = []
        for i, element in enumerate(elements):
            try:
                element_screenshot_path = os.path.join(screenshots_dir, f"element_{i}.png")
                if take_element_screenshot(driver, element, element_screenshot_path):
                    element_screenshots.append(element_screenshot_path)
                    print(f"Element {i} screenshot saved to {element_screenshot_path}")
            except Exception as e:
                print(f"Error capturing element {i}: {str(e)}")
                continue
        
        # Get results data
        results = []
        data_elements = driver.find_elements(By.CSS_SELECTOR, "div[data-index]")
        
        for element in data_elements:
            try:
                data_index = element.get_attribute("data-index")
                content_div = element.find_element(By.CSS_SELECTOR, "div.flex-1.min-w-0.flex.flex-col")
                
                timestamp = content_div.find_element(By.CSS_SELECTOR, "span.text-gray-500").text
                title = content_div.find_element(By.CSS_SELECTOR, "span.font-medium").text
                description = content_div.find_element(By.CSS_SELECTOR, "span.text-gray-700").text
                
                results.append({
                    "index": data_index,
                    "timestamp": timestamp,
                    "title": title,
                    "description": description,
                    "screenshot": element_screenshots[int(data_index)] if data_index.isdigit() and int(data_index) < len(element_screenshots) else None
                })
            except Exception as e:
                print(f"Error processing element {element.get_attribute('data-index')}: {str(e)}")
                continue
        
        print(f"Found {len(results)} results")
        
        # Save results to JSON
        results_file = screenshot_path.replace('.png', '.json')
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Take full page screenshot
        driver.save_screenshot(screenshot_path)
        print(f"Full page screenshot saved to {screenshot_path}")
        print(f"Results saved to {results_file}")
        
        return True, results_file, element_screenshots
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return False, None, None

def main():
    if len(sys.argv) != 4:
        print("Usage: python new.py <video_url> <prompt> <screenshot_path>")
        sys.exit(1)
    
    video_url = sys.argv[1]
    prompt = sys.argv[2]
    screenshot_path = sys.argv[3]
    
    ACCOUNT_EMAIL = "m17902133@gmail.com"
    ACCOUNT_PASSWORD = "marlen00878"
    driver_path = "C:/chromedriver-win64/chromedriver.exe"
    
    try:
        print("Initializing browser...")
        service = Service(executable_path=driver_path)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(service=service, options=options)
        
        if not login(driver, ACCOUNT_EMAIL, ACCOUNT_PASSWORD):
            print("Failed to login. Script stopped.")
            sys.exit(1)
        
        success, results_file, element_screenshots = process_video(driver, video_url, prompt, screenshot_path)
        
        if not success:
            print("Failed to process video")
            sys.exit(1)
            
        print("\nElement screenshots saved at:")
        for screenshot in element_screenshots:
            print(screenshot)
            
        return results_file
            
    except Exception as e:
        print(f"Critical error: {str(e)}")
        sys.exit(1)
    finally:
        if 'driver' in locals():
            input("Press Enter to close browser...")
            driver.quit()
            print("Browser closed.")

if __name__ == "__main__":
    main()