import logging
import re
from dataclasses import dataclass
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from feedparser import FeedParserDict
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from offer import Offer
from scrapper_base import ScrapperBase


class LastMinuter(ScrapperBase):
    def __init__(self):
        super().__init__(cache_path=Path('lastminuter_cache.pkl.zstd'))
        self.rss_url = 'https://www.lastminuter.pl/feed'
        self.offer_link_locator = (By.XPATH, "//div[@class='deal__button']/a")

    def get_lastminuter_entries(self) -> list[FeedParserDict]:
        rss = requests.get(self.rss_url)
        feed = feedparser.parse(rss.text)
        return feed.entries

    @staticmethod
    def get_lastminuter_offer_category(url: str) -> str:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        if span := soup.find('span', {'class': 'deals__valid_until'}):
            text = span.get_text().replace('Termin ', '')
        else:
            text = ''
        section = soup.find('section', {'id': 'offer_page'})
        if not section:
            return text

        spans = section.find_all('span')  # find all span elements
        for span in spans:
            if img := span.find('img', alt='clock icon') or span.find(
                    'img', alt='boarding icon'
            ):
                text = f'{text} {span.get_text()}'
        return text

    def lastminuter_to_offer(self, feed: FeedParserDict, driver: webdriver.Chrome,wait: WebDriverWait) -> Offer:
        pattern = r'(od|za)\s*\d+\s*zł'
        title = feed.title
        price = re.search(pattern, title)
        if price:
            price = price.group()
            title = re.sub(price, '', title)

        driver.get(feed.link)
        try:
            offer_link_element = wait.until(
                EC.presence_of_element_located(self.offer_link_locator)
            )
            offer_link = offer_link_element.get_attribute('href')
        except TimeoutException:
            offer_link = feed.link

        return Offer(offer_link, title, price, self.get_lastminuter_offer_category(feed.link))

    def get_offers(self, driver: webdriver.Chrome) -> list[Offer]:
        lastminuter_entries = self.get_lastminuter_entries()
        wait = WebDriverWait(driver, 20)
        offers = [self.lastminuter_to_offer(e, driver, wait) for e in lastminuter_entries]
        offers = [offer for offer in offers if offer not in self.cache]
        for offer in offers:
            self.cache.add(offer)
        logging.info(f"Found {len(offers)} lastminiuter offers")
        return offers
