import contextlib
import logging
import pickle
import re
import time
from pathlib import Path

import feedparser
import requests
import schedule
import yagmail
import yaml
from bs4 import BeautifulSoup
from easydict import EasyDict
from feedparser import FeedParserDict
from jinja2 import Template
from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
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
    button = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='Akceptuj wszystko']"))
    )
    # Accept cookies
    button.click()
    divs = WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.XPATH, "//div[starts-with(@style, 'order')]"))
    )
    return divs


def create_wakacyjni_piraci_offers(filtered_divs: list[WebElement]) -> list[EasyDict]:
    wakacyjni_piraci_offers = []
    for d in filtered_divs:
        a = d.find_element(By.TAG_NAME, 'a')
        href = a.get_attribute('href')
        splitted_text = d.text.split('\n')
        if 'inclusive' not in d.text.lower():
            continue
        # remove publish date
        indexes_to_ignore = set()
        price_str = main_category = sub_category = ''
        for i, s in enumerate(splitted_text):
            if s.lower().strip().startswith(('za', 'od')):
                price_str = s.strip()
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
    rss = requests.get(rss_url, verify=VERIFY_SSL)
    feed = feedparser.parse(rss.text)
    return feed.entries


def get_lastminuter_offer_category(url: str) -> str:
    response = requests.get(url, verify=VERIFY_SSL)
    soup = BeautifulSoup(response.text, 'html.parser')
    span = soup.find('span', {'class': 'deals__valid_until'})
    text = ''
    if span:
        text = span.get_text().replace('Termin ', '')

    section = soup.find('section', {'id': 'offer_page'})
    if not section:
        return text

    spans = section.find_all('span')  # find all span elements
    for span in spans:
        img = span.find('img', alt='clock icon')
        if not img:
            img = span.find('img', alt='boarding icon')
        if img:
            text = f'{text} {span.get_text()}'
    return text


def lastminuter_to_offer(feed: FeedParserDict) -> EasyDict:
    pattern = r'(od|za)\s*\d+\s*zł'
    title = feed.title
    price = re.search(pattern, title)
    if price:
        price = price.group()
        title = re.sub(price, '', title)
    return EasyDict(link=feed.link, title=title, price_str=price, category=get_lastminuter_offer_category(feed.link))


def get_fly4free_divs(driver: webdriver.Chrome, category: str, is_first_call: bool = False) -> list[WebElement]:
    if category in {'first-minute', 'wakacje'}:
        driver.get(f'https://www.fly4free.pl/tag/{category}/')
    else:
        driver.get(f'https://www.fly4free.pl/tanie-loty/{category}/')
    if is_first_call:
        with contextlib.suppress(TimeoutException):
            button = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//button[normalize-space()='ZGADZAM SIĘ']"))
            )
            # Accept cookies
            button.click()
    offers_div = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'row-equal'))
    )
    offers_divs = offers_div.find_elements(By.XPATH, "./div[contains(@class, 'col-xs-12')]")

    filtered_offers_divs = []
    for offer_div in offers_divs:
        # Check if the div has a direct child div with the class 'item--soldout'
        soldout_divs = offer_div.find_elements(By.XPATH, "./div[contains(@class, 'item--soldout')]")

        # If it doesn't have such a child div, add it to the filtered list
        if not soldout_divs:
            filtered_offers_divs.append(offer_div)
    return filtered_offers_divs


def get_fly4free_category_offers(offers_divs: list[WebElement], category: str) -> list[EasyDict]:
    offers = []
    for offer_div in offers_divs:
        try:
            price_div = offer_div.find_element(By.CLASS_NAME, 'item__price')
        except NoSuchElementException:
            continue

        price_text = price_div.text
        if category == 'loty':
            price_int = int(re.search(r'\d+', price_text).group())
            if price_int > 1000:
                continue
        if category in {'wczasy', 'wakacje', 'first-minute'}:
            category = 'wczasy'

        title = offer_div.find_element(By.CLASS_NAME, 'item__title')
        a_tag = title.find_element(By.TAG_NAME, 'a')
        title = a_tag.text
        if 'inclusive' not in title.lower():
            continue
        href = a_tag.get_attribute('href')
        offer = EasyDict(
            category=category,
            price_str=price_text,
            title=title,
            link=href
        )
        offers.append(offer)
    return offers


def send_mail(html_content: str) -> None:
    with open('secrets.yml', 'rt') as f:
        secrets = EasyDict(yaml.safe_load(f))
    email_subject = 'Oferty wakacje'
    yag = yagmail.SMTP(secrets.src_mail, secrets.src_pwd, port=587, smtp_starttls=True, smtp_ssl=False)
    yag.send(to=secrets.dst_mail, subject=email_subject, contents=(html_content, 'text/html'))


def load_from_cache(previous_piraci_offers: list, previous_lastminuter_offers: list, previous_fly4free_offers: list):
    cache = Path('previous_offers.pkl')
    if cache.exists():
        with cache.open('rb') as f:
            unpickled_cache = pickle.load(f)
        previous_piraci_offers.extend(unpickled_cache['previous_piraci_offers'])
        previous_lastminuter_offers.extend(unpickled_cache['previous_lastminuter_offers'])
        previous_fly4free_offers.extend(unpickled_cache['previous_fly4free_offers'])


LASTMINUTER_RSS_URL = 'https://www.lastminuter.pl/feed'

previous_lastminuter_offers = []
previous_piraci_offers = []
previous_fly4free_offers = []


def main():
    global previous_piraci_offers, previous_lastminuter_offers, previous_fly4free_offers

    load_from_cache(previous_piraci_offers, previous_lastminuter_offers, previous_fly4free_offers)

    lastminuter_entries = get_lastminuter_entries(LASTMINUTER_RSS_URL)
    offers = [lastminuter_to_offer(e) for e in lastminuter_entries]
    offers = [offer for offer in offers if offer not in previous_lastminuter_offers]
    previous_lastminuter_offers = [*previous_lastminuter_offers, *offers][-300:]
    driver = get_driver()
    divs = get_wakacyjni_piraci_divs(driver)

    # 18 elements on page -> others are trash
    filtered_divs = [div for div in divs[:18] if re.search(r'(Za|Od)', div.text)]
    if not filtered_divs:
        print('Wakacyjni piraci - nic nie znaleziono')
    piraci_offers = create_wakacyjni_piraci_offers(filtered_divs)
    piraci_offers = [offer for offer in piraci_offers if offer not in previous_piraci_offers]
    offers.extend(piraci_offers)
    previous_piraci_offers = [*previous_piraci_offers, *piraci_offers][-300:]

    categories = ('loty', 'wczasy', 'weekend', 'wakacje', 'first-minute')
    all_fly4free_offers = []
    for i, cat in enumerate(categories):
        filtered_offers_divs = get_fly4free_divs(driver, cat, is_first_call=(i == 0))
        fly4free_offers = get_fly4free_category_offers(filtered_offers_divs, cat)
        for offer in fly4free_offers:
            if (offer not in all_fly4free_offers) and (offer not in previous_fly4free_offers):
                all_fly4free_offers.append(offer)

    offers.extend(all_fly4free_offers)
    previous_fly4free_offers = [*previous_fly4free_offers, *all_fly4free_offers][-200:]

    driver.close()

    html_content = render_html(offers)
    with open('holidays.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    with open('previous_offers.pkl', 'wb') as f:
        pickle.dump(
            dict(
                previous_fly4free_offers=previous_fly4free_offers,
                previous_piraci_offers=previous_piraci_offers,
                previous_lastminuter_offers=previous_lastminuter_offers
            ), f, pickle.HIGHEST_PROTOCOL
        )

    send_mail(html_content)


VERIFY_SSL = True
if __name__ == '__main__':
    logging.basicConfig(filename='error.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    schedule.every().day.at("12:00").do(main)
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logging.exception("An error occurred:")
            print(e)
            time.sleep(60*60)
        time.sleep(1)
    # main()
