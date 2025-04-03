import time
import random
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException, StaleElementReferenceException

MAX_PAGES = 3

def human_sleep(min_time=0.5, max_time=1):
    time.sleep(random.uniform(min_time, max_time))

def close_popup(driver):
    try:
        popups = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Close') or contains(text(), 'Close')]")
        for popup in popups:
            popup.click()
            print("Popup closed!")
            human_sleep()
    except Exception as e:
        print(f"No popups to close or failed: {e}")

def extract_job_description(driver):
    job_desc = {}
    try:
        possible_containers = [
            "styles_job-desc-container__txpYf",
            "job-desc",
            "job-description",
            "jd-container"
        ]
        desc_container = None
        for container_class in possible_containers:
            try:
                desc_container = driver.find_element(By.CLASS_NAME, container_class)
                break
            except NoSuchElementException:
                continue
        if not desc_container:
            return job_desc
        desc_classes = [
            "styles_JDC__dang-inner-html__h0K4t",
            "job-desc-content",
            "description",
            "jd-details"
        ]
        for desc_class in desc_classes:
            try:
                main_desc = desc_container.find_element(By.CLASS_NAME, desc_class).text
                if main_desc.strip():
                    job_desc["Description"] = main_desc
                break
            except NoSuchElementException:
                continue
    except NoSuchElementException:
        pass
    return job_desc

def scrape_indeed(job_search, years_of_experience, location):
    job_data = []
    processed_urls = set()
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 10)
        print("Starting Indeed scraping...")
        driver.get("https://www.indeed.com")
        human_sleep()
        close_popup(driver)
        search_box = wait.until(EC.element_to_be_clickable((By.ID, "text-input-what")))
        search_box.send_keys(f"{job_search} {years_of_experience} years experience")
        if location:
            location_box = wait.until(EC.element_to_be_clickable((By.ID, "text-input-where")))
            location_box.clear()
            location_box.send_keys(location)
        search_box.send_keys(Keys.RETURN)
        human_sleep()
        for page in range(MAX_PAGES):
            print(f"Scraping Indeed page {page + 1}")
            try:
                jobs = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class, 'jcs-JobTitle')]")))
                for i, job in enumerate(jobs):
                    try:
                        job_url = job.get_attribute("href")
                        if job_url in processed_urls:
                            continue
                        processed_urls.add(job_url)
                        job.click()
                        human_sleep()
                        wait.until(EC.presence_of_element_located((By.ID, "jobDescriptionText")))
                        job_title = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "jobsearch-JobInfoHeader-title"))).text or "Not found"
                        company_name = driver.find_element(By.CSS_SELECTOR, ".css-nj0gl .jobsearch-JobInfoHeader-companyNameLink").text if driver.find_elements(By.CSS_SELECTOR, ".css-nj0gl .jobsearch-JobInfoHeader-companyNameLink") else "Not found"
                        job_desc = driver.find_element(By.ID, "jobDescriptionText").text if driver.find_elements(By.ID, "jobDescriptionText") else ""
                        job_data.append({"Job URL": job_url, "Job Title": job_title, "Company": company_name, "Job Description": {"Description": job_desc}})
                        print(f"Scraped Indeed job {i + 1}: {job_title} - {company_name}")
                        human_sleep()
                    except Exception as e:
                        print(f"Error scraping Indeed job {i + 1}: {e}")
                if page < MAX_PAGES - 1:
                    next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Next Page']")))
                    next_button.click()
                    human_sleep()
            except Exception as e:
                print(f"Error on Indeed page {page + 1}: {e}")
                break
    except Exception as e:
        print(f"Indeed scraping failed: {e}")
    finally:
        if driver:
            driver.quit()
    return job_data

def scrape_naukri(job_search, years_of_experience, location):
    job_data = []
    processed_urls = set()
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = webdriver.Chrome(options=options)
        driver.minimize_window()  # Minimize the browser window
        wait = WebDriverWait(driver, 10)
        print("Starting Naukri scraping...")
        driver.get("https://www.naukri.com")
        human_sleep()
        close_popup(driver)
        search_box = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Enter skills / designations / companies']")))
        search_box.send_keys(job_search)
        if years_of_experience:
            exp_box = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Select experience']")))
            exp_box.send_keys(years_of_experience)
        if location:
            location_box = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Enter location']")))
            location_box.send_keys(location)
        search_box.send_keys(Keys.RETURN)
        human_sleep()
        for page in range(MAX_PAGES):
            print(f"Scraping Naukri page {page + 1}")
            try:
                jobs = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "title")))
                main_window = driver.current_window_handle
                for i, job in enumerate(jobs):
                    try:
                        job_url = job.get_attribute("href")
                        if job_url in processed_urls:
                            print(f"Skipping duplicate job {i + 1}: {job_url}")
                            continue
                        processed_urls.add(job_url)
                        job.click()
                        human_sleep()
                        wait.until(lambda d: len(d.window_handles) > 1)
                        driver.switch_to.window([w for w in driver.window_handles if w != main_window][0])
                        job_title = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1"))).text or "Not found"
                        company_name = driver.find_element(By.CLASS_NAME, "styles_jd-header-comp-name__MvqAI").find_element(By.TAG_NAME, "a").text if driver.find_elements(By.CLASS_NAME, "styles_jd-header-comp-name__MvqAI") else "Not found"
                        job_desc = extract_job_description(driver)
                        job_data.append({"Job URL": job_url, "Job Title": job_title, "Company": company_name, "Job Description": job_desc})
                        print(f"Scraped Naukri job {i + 1}: {job_title} - {company_name}")
                        driver.close()
                        driver.switch_to.window(main_window)
                        human_sleep()
                    except Exception as e:
                        print(f"Error scraping Naukri job {i + 1}: {e}")
                        if len(driver.window_handles) > 1:
                            driver.close()
                        driver.switch_to.window(main_window)
                if page < MAX_PAGES - 1:
                    next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Next')]")))
                    next_button.click()
                    human_sleep()
            except Exception as e:
                print(f"Error on Naukri page {page + 1}: {e}")
                break
    except Exception as e:
        print(f"Naukri scraping failed: {e}")
    finally:
        if driver:
            driver.quit()
    return job_data

def scrape_jobs(job_title, resume_json=None):
    """
    Scrape jobs from Indeed and Naukri based on job title and resume data.
    Args:
        job_title (str): Job title to search for
        resume_json (dict): Parsed resume data (optional)
    Returns:
        list: List of job dictionaries with title, company, and description
    """
    years_of_experience = "3"  # Default
    if resume_json and "experience" in resume_json:
        total_years = 0
        for exp in resume_json.get("experience", []):
            duration = exp.get("duration", "")
            if "year" in duration.lower():
                try:
                    years = int(''.join(filter(str.isdigit, duration)))
                    total_years += years
                except ValueError:
                    pass
        years_of_experience = str(total_years) if total_years > 0 else "3"
    location = "Bangalore"  # Default location
    indeed_jobs = scrape_indeed(job_title, years_of_experience, location)
    naukri_jobs = scrape_naukri(job_title, years_of_experience, location)
    all_jobs = indeed_jobs + naukri_jobs
    unique_jobs = []
    seen_urls = set()
    for job in all_jobs:
        job_key = f"{job.get('Job Title', '')} - {job.get('Company', '')}"
        if job_key not in seen_urls:
            seen_urls.add(job_key)
            unique_jobs.append(job)
    with open("scraped_jobs.json", "w") as f:
        json.dump(unique_jobs, f, indent=4)
    return unique_jobs

if __name__ == "__main__":
    jobs = scrape_jobs("Software Developer")
    print(f"Total jobs scraped: {len(jobs)}")