import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def configurar_chrome():
    chrome_options = Options()
    chrome_options.add_argument('--window-size=1920,1080')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

driver = configurar_chrome()
wait = WebDriverWait(driver, 60)

try:
    print("Iniciando inspeção de IDs...")
    driver.get("https://harpixfat.mezenergia.com/FAT/open.do?sys=FAT")
    driver.switch_to.frame("mainform")
    campo = wait.until(EC.presence_of_element_located((By.ID, "WFRInput1051800")))
    campo.send_keys("4284")
    driver.find_element(By.XPATH, "//button[contains(., 'Entrar')]").click()
    time.sleep(10)
    
    driver.switch_to.default_content()
    wait.until(EC.frame_to_be_available_and_switch_to_it("mainsystem"))
    wait.until(EC.frame_to_be_available_and_switch_to_it("mainform"))
    
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    url_frame = next((f.get_attribute('name') for f in frames if f.get_attribute('name').startswith('URLFrame')), None)
    print(f"URLFrame: {url_frame}")
    
    wait.until(EC.frame_to_be_available_and_switch_to_it(url_frame))
    wait.until(EC.frame_to_be_available_and_switch_to_it("mainform"))
    
    print("Dumping todos os IDs de elementos clicáveis...")
    elements = driver.find_elements(By.XPATH, "//*[@id or @onclick or @class]")
    with open("detected_ids.txt", "w", encoding="utf-8") as f:
        for el in elements:
            try:
                tag = el.tag_name
                eid = el.get_attribute("id")
                cls = el.get_attribute("class")
                txt = el.text.strip()
                if eid or txt:
                    f.write(f"Tag: {tag} | ID: {eid} | Class: {cls} | Text: {txt}\n")
            except: continue
    print("Cuidando para não fechar...")
    time.sleep(30)

finally:
    driver.quit()
