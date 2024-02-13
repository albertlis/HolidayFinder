import logging
import re
import time

import feedparser
import requests
import schedule
import yagmail
import yaml
from easydict import EasyDict
from feedparser import FeedParserDict
from jinja2 import Template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def get_driver() -> webdriver.Chrome:
    op = webdriver.ChromeOptions()
    op.add_argument('--headless')
    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=op)


def get_wakacyjni_piraci_divs(driver: webdriver.Chrome) -> list[WebElement]:
    driver.get('https://www.wakacyjnipiraci.pl')
    button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Akceptuj wszystko']"))
    )
    # Accept cookies
    button.click()
    divs = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[starts-with(@style, 'order')]"))
    )
    return divs


def create_wakacyjni_piraci_offers(filtered_divs: list[WebElement]) -> list[EasyDict]:
    wakacyjni_piraci_offers = []
    for d in filtered_divs:
        a = d.find_element(By.TAG_NAME, 'a')
        href = a.get_attribute('href')
        splitted_text = d.text.split('\n')
        # remove publish date
        _ = splitted_text.pop()
        indexes_to_ignore = set()
        price_str = main_category = sub_category = ''
        for i, s in enumerate(splitted_text):
            if s.upper().strip() in {'ZA', 'OD'}:
                price_str = ' '.join([s.strip(), splitted_text[i + 1].strip()])
                del splitted_text[i + 1]
                del splitted_text[i]
                break

        for i, s in enumerate(splitted_text):
            if all(letter.isupper() for letter in s.strip()):
                main_category = s.strip()
                indexes_to_ignore.add(i)
                if i > 0:
                    sub_category = splitted_text[i - 1]
                    indexes_to_ignore.add(i - 1)
        left_text_lines = [s for i, s in enumerate(splitted_text) if i not in indexes_to_ignore]
        title = ''.join(left_text_lines)
        wakacyjni_piraci_offers.append(
            EasyDict(
                category=f'{main_category} {sub_category}'.strip(),
                price_str=price_str,
                title=title,
                link=href
            )
        )
    return wakacyjni_piraci_offers


def render_html(offers: list[EasyDict]) -> str:
    with open('template.html', 'rt', encoding='utf-8') as f:
        html_template = f.read()
    template = Template(html_template)
    return template.render(offers=offers)


def get_lastminuter_entries(rss_url: str) -> list[FeedParserDict]:
    rss = requests.get(rss_url)  # , verify=False)
    feed = feedparser.parse(rss.text)
    return feed.entries


def lastminuter_to_offer(feed: FeedParserDict) -> EasyDict:
    pattern = r'(od|za)\s*\d+\s*zł'
    title = feed.title
    price = re.search(pattern, title)
    if price:
        price = price.group()
        title = re.sub(price, '', title)
    return EasyDict(link=feed.link, title=title, price_str=price, category='')


def send_mail(html_content: str) -> None:
    with open('secrets.yml', 'rt') as f:
        secrets = EasyDict(yaml.safe_load(f))
    email_subject = 'Oferty wakacje'
    yag = yagmail.SMTP(secrets.scr_mail, secrets.src_pwd, port=587, smtp_starttls=True)  # , smtp_ssl=False)
    yag.send(to=secrets.dst_mail, subject=email_subject, contents=(html_content, 'text/html'))


LASTMINUTER_RSS_URL = 'https://www.lastminuter.pl/feed'

previous_lastminuter_offers = []
previous_piraci_offers = []


def main():
    global previous_piraci_offers, previous_lastminuter_offers
    lastminuter_entries = get_lastminuter_entries(LASTMINUTER_RSS_URL)
    offers = [lastminuter_to_offer(e) for e in lastminuter_entries]
    offers = [offer for offer in offers if offer not in previous_lastminuter_offers]
    driver = get_driver()
    divs = get_wakacyjni_piraci_divs(driver)

    filtered_divs = [div for div in divs[:18] if re.search(r'(ZA\n|OD\n)', div.text)]
    piraci_offers = create_wakacyjni_piraci_offers(filtered_divs)
    piraci_offers = [offer for offer in piraci_offers if offer not in previous_piraci_offers]
    offers.extend(piraci_offers)
    previous_piraci_offers = piraci_offers

    driver.close()

    html_content = render_html(offers)
    # with open('holidays.html', 'w', encoding='utf-8') as f:
    #     f.write(html_content)

    send_mail(html_content)


if __name__ == '__main__':
    logging.basicConfig(filename='error.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    schedule.every().day.at("13:00").do(main)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logging.exception("An error occurred:")
        time.sleep(1)
    # main()
