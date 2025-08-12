import undetected_chromedriver as uc
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

import os
import pandas as pd
import hashlib
import pyperclip


LOG_FILE = "log_01"

def load_logged_posts():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def append_log(post_id):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{post_id}\n")

def clear_log():
    open(LOG_FILE, "w").close()


# Tes identifiants LinkedIn
LINKEDIN_EMAIL = "jaxavo6937@elobits.com"
LINKEDIN_PASSWORD = "COSMA4ever#1"

def login_to_linkedin(driver):
    driver.get("https://www.linkedin.com/login")
    time.sleep(3)
    driver.find_element(By.ID, "username").send_keys(LINKEDIN_EMAIL)
    driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD + Keys.RETURN)
    time.sleep(15)

def go_to_hashtag_page(driver, hashtag):
    driver.get("https://www.linkedin.com/feed/")
    time.sleep(5)
    search_bar = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'Recherche') or contains(@placeholder, 'Search')]")
    search_bar.clear()
    search_bar.send_keys(hashtag)
    search_bar.send_keys(Keys.RETURN)
    time.sleep(5)

    buttons = driver.find_elements(By.XPATH, "//button | //span")
    for btn in buttons:
        if btn.text.strip().lower() in ["publications", "posts"]:
            btn.click()
            break
    time.sleep(5)

    try:
        all_filters_button = driver.find_element(By.XPATH, "//button[contains(@class,'search-reusables__all-filters-pill-button') and contains(., 'Tous les filtres')]")
        all_filters_button.click()
        time.sleep(3)

        recent_label = driver.find_element(By.XPATH, "//label[@for='advanced-filter-sortBy-date_posted']")
        recent_label.click()
        time.sleep(2)

        images_label = driver.find_element(By.XPATH, "//label[@for='advanced-filter-contentType-photos']")
        images_label.click()
        time.sleep(2)

        show_results_button = driver.find_element(By.XPATH, "//button[@data-test-reusables-filters-modal-show-results-button='true']")
        driver.execute_script("arguments[0].scrollIntoView(true);", show_results_button)
        driver.execute_script("arguments[0].click();", show_results_button)
        time.sleep(5)

    except Exception as e:
        print("Erreur lors de l'application des filtres :", e)

def is_job_post(post):
    try:
        if post.find_element(By.CSS_SELECTOR, "button[data-control-name='jobdetails_topcard_inapply']"):
            return True
    except:
        pass
    try:
        if post.find_element(By.CSS_SELECTOR, "a[href*='/jobs/']"):
            return True
    except:
        pass
    try:
        labels = post.find_elements(By.CSS_SELECTOR, "span")
        for label in labels:
            if "offre d'emploi" in label.text.lower() or "emploi" in label.text.lower():
                return True
    except:
        pass
    return False

def generate_post_id(author, post_text):
    base = f"{author or ''}-{post_text or ''}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def get_post_link(driver, post):
    """Extrait le lien du post en utilisant le bouton Envoyer"""
    post_url = None
    
    try:
        # 1. Cliquer sur le bouton "Envoyer"
        send_btn = post.find_element(By.CSS_SELECTOR, "button[aria-label*='Envoyer dans un message privé']")
        driver.execute_script("arguments[0].scrollIntoView(true);", send_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", send_btn)
        time.sleep(2)
        print(f"Bouton 'Envoyer' clique")
        
        # 2. Cliquer sur "Copier le lien vers le post"
        copy_link_btn = driver.find_element(By.XPATH, "//span[text()='Copier le lien vers le post']/ancestor::button")
        driver.execute_script("arguments[0].click();", copy_link_btn)
        time.sleep(2)
        print(f"Bouton 'Copier le lien' clique")
        
        # 3. Récupérer le lien du presse-papiers
        try:
            post_url = pyperclip.paste()
            print(f"Lien du post copie : {post_url}")
        except Exception as e:
            print(f"Erreur lors de la recuperation du presse-papiers : {e}")
        
        # 4. Fermer la modale
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Ignorer'].artdeco-modal__dismiss")
            driver.execute_script("arguments[0].click();", close_btn)
            time.sleep(2)
            print(f"Modale fermee")
        except Exception as e:
            print(f"Erreur lors de la fermeture de la modale : {e}")
    
    except Exception as e:
        print(f"Erreur lors de l'extraction du lien du post : {e}")
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Ignorer'].artdeco-modal__dismiss")
            driver.execute_script("arguments[0].click();", close_btn)
            time.sleep(2)
        except:
            pass
    
    return post_url

def extract_post_data(driver, post, idx, feed_url):
    try:
        try:
            driver.execute_script("arguments[0].scrollIntoView();", post)
        except:
            print(f"Scroll impossible pour post #{idx+1}")
            return None
        time.sleep(1)
        
        print(f"Extraction du lien pour le post #{idx+1}...")
        post_url = get_post_link(driver, post)
        
        current_url = driver.current_url
        post.click()
        time.sleep(3)

        if driver.current_url != current_url:
            print(f"Post #{idx+1} est un repost détecté par URL, ignoré.")
            driver.get(feed_url)
            time.sleep(5)
            for _ in range(idx + 2):
                driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(0.5)
            return None

        try:
            post_text = driver.find_element(By.CSS_SELECTOR,
                "div.feed-shared-inline-show-more-text.feed-shared-update-v2__description").text.strip()
        except:
            post_text = None

        try:
            author_span = driver.find_element(By.CSS_SELECTOR,
                "span.hoverable-link-text.t-14.t-bold.text-body-medium-bold.white-space-nowrap.t-black")
            author_name_preview = author_span.text.strip()
            driver.execute_script("arguments[0].scrollIntoView(true);", author_span)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", author_span)
            time.sleep(5)

            profile_url = driver.current_url

            try:
                name = driver.find_element(By.CSS_SELECTOR, "h1.text-heading-xlarge").text.strip()
            except:
                name = None

            try:
                role = driver.find_element(By.CSS_SELECTOR, "div.text-body-medium.break-words").text.strip()
            except:
                role = None

            city = country = None
            try:
                location_elem = driver.find_element(By.CSS_SELECTOR,
                    "span.text-body-small.inline.t-black--light.break-words")
                location = location_elem.text.strip()
                parts = location.split(",")
                city = parts[0].strip()
                if len(parts) > 1:
                    country = ", ".join([p.strip() for p in parts[1:]])
            except:
                city = None
                country = None

            driver.get(feed_url)
            time.sleep(3)
            for _ in range(idx + 2):
                driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(0.5)

        except Exception as e:
            print(f"Erreur extraction auteur post #{idx+1}: {e}")
            name = None
            role = None
            city = None
            country = None
            author_name_preview = None
            profile_url = None

        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "button.artdeco-modal__dismiss")
            close_btn.click()
            time.sleep(2)
        except:
            pass

        return {
            'post_id': generate_post_id(name or author_name_preview, post_text),
            'post_text': post_text,
            'post_url': post_url,  
            'author_name': name or author_name_preview,
            'author_role': role,
            'profile_url': profile_url,
            'city': city,
            'country': country
        }

    except Exception as e:
        print(f"Erreur générale post #{idx+1} : {e}")
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "button.artdeco-modal__dismiss")
            close_btn.click()
            time.sleep(2)
        except:
            pass
        return None

def main():
    options = uc.ChromeOptions()
    prefs = {
        "profile.default_content_setting_values.clipboard": 1,
        "profile.default_content_setting_values.notifications": 1
    }
    options.add_experimental_option("prefs", prefs)
    driver = uc.Chrome(options=options, version_main=138)

    login_to_linkedin(driver)

    # Load already logged posts
    logged_posts = load_logged_posts()

    try:
        with open("keywords.txt", "r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier keywords.txt : {e}")
        return

    all_data = []

    for keyword in keywords:
        print(f"\n==== Traitement du mot-clé : {keyword} ====")
        go_to_hashtag_page(driver, keyword)
        feed_url = driver.current_url

        data_list = []
        seen_post_ids = set()
        post_index = 0
        MAX_POSTS = 20
        scroll_attempts = 0
        MAX_SCROLLS = 70

        while len(data_list) < MAX_POSTS and scroll_attempts < MAX_SCROLLS:
            posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2")

            while post_index < len(posts) and len(data_list) < MAX_POSTS:
                try:
                    posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2")
                    post = posts[post_index]
                except Exception as e:
                    print(f"Post #{post_index+1} ignoré (stale element): {e}")
                    post_index += 1
                    continue

                if is_job_post(post):
                    print(f"Post #{post_index+1} est une offre d'emploi, ignoré.")
                    post_index += 1
                    continue

                data = extract_post_data(driver, post, post_index, feed_url)
                if data:
                    if data['post_id'] in logged_posts:
                        print(f"Post #{post_index+1} déjà loggé, ignoré.")
                        post_index += 1
                        continue
                    if data['post_id'] in seen_post_ids:
                        print(f"Post #{post_index+1} déjà vu, ignoré.")
                        post_index += 1
                        continue
                    seen_post_ids.add(data['post_id'])
                    append_log(data['post_id'])
                    logged_posts.add(data['post_id'])
                    data['keyword'] = keyword
                    data_list.append(data)
                    print(f"Post #{post_index+1} extrait. Total: {len(data_list)}/{MAX_POSTS}")

                post_index += 1

            if len(data_list) < MAX_POSTS:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                print("Scroll supplémentaire... en attente de nouveaux posts.")
                time.sleep(7)
                scroll_attempts += 1

        all_data.extend(data_list)

    df = pd.DataFrame(all_data)
    df.drop_duplicates(subset=["post_id"], inplace=True)
    
    # Save results: append to Scraped.xlsx if exists
    output_file = 'Scraped.xlsx'
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_excel(output_file)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.drop_duplicates(subset=["post_id"], inplace=True)
            combined_df.to_excel(output_file, index=False)
            print("Données ajoutées à Scraped.xlsx existant.")
        except Exception as e:
            print(f"Impossible d'ajouter à Scraped.xlsx : {e}")
    else:
        df.to_excel(output_file, index=False)
        print("Scraped.xlsx créé avec les données.")
    print("Extraction terminée.")

    driver.quit()

if __name__ == "__main__":
    main()
