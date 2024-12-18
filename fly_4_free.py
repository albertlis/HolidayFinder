import contextlib
import logging
import re
from pathlib import Path

from selenium import webdriver
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from offer import Offer
from scrapper_base import ScrapperBase


class Fly4Free(ScrapperBase):
    def __init__(self):
        super().__init__(cache_path=Path('fly4free_cache.pkl.zstd'))
        self.categories = ('loty', 'wczasy', 'weekend', 'wakacje', 'first-minute')
        self.tag_url = 'https://www.fly4free.pl/tag'
        self.cheap_flights_url = 'https://www.fly4free.pl/tanie-loty'
        self.accept_cookies_locator = (By.XPATH, "//button[normalize-space()='ZGADZAM SIĘ']")
        self.offer_div_locator = (By.CLASS_NAME, 'row-equal')
        self.offer_divs_locator = (By.XPATH, "./div[contains(@class, 'col-xs-12')]")
        self.soldout_locator = (By.XPATH, "./div[contains(@class, 'item--soldout')]")
        self.price_locator = (By.CLASS_NAME, 'item__price')
        self.title_locator = (By.CLASS_NAME, 'item__title')
        self.flight_price_limit = 1000

    def get_fly4free_divs(self, driver: webdriver.Chrome, category: str, is_first_call: bool = False) -> list[
        WebElement]:
        wait = WebDriverWait(driver, 20)
        if category in {'first-minute', 'wakacje'}:
            driver.get(f'{self.tag_url}/{category}/')
        else:
            driver.get(f'{self.cheap_flights_url}/{category}/')
        if is_first_call:
            with contextlib.suppress(TimeoutException):
                button = wait.until(EC.presence_of_element_located(self.accept_cookies_locator))
                # Accept cookies
                button.click()
        offers_div = wait.until(EC.presence_of_element_located(self.offer_div_locator))
        offers_divs = offers_div.find_elements(*self.offer_divs_locator)

        filtered_offers_divs = []
        for offer_div in offers_divs:
            # Check if the div has a direct child div with the class 'item--soldout'
            soldout_divs = offer_div.find_elements(*self.soldout_locator)

            # If it doesn't have such a child div, add it to the filtered list
            if not soldout_divs:
                filtered_offers_divs.append(offer_div)
        return filtered_offers_divs

    def get_fly4free_category_offers(self, offers_divs: list[WebElement], category: str) -> list[Offer]:
        offers = []
        for offer_div in offers_divs:
            try:
                price_div = offer_div.find_element(*self.price_locator)
            except NoSuchElementException:
                continue

            price_text = price_div.text
            if category == 'loty':
                price_int = int(re.search(r'\d+', price_text).group())
                if price_int > self.flight_price_limit:
                    continue
            if category in {'wczasy', 'wakacje', 'first-minute'}:
                category = 'wczasy'

            title = offer_div.find_element(*self.title_locator)
            a_tag = title.find_element(By.TAG_NAME, 'a')
            title = a_tag.text
            if 'inclusive' not in title.lower():
                continue
            href = a_tag.get_attribute('href')
            offer = Offer(href, title, price_text, category)
            offers.append(offer)
        return offers

    def get_offers(self, driver: webdriver.Chrome) -> list[Offer]:

        all_fly4free_offers = []
        for i, cat in enumerate(self.categories):
            filtered_offers_divs = self.get_fly4free_divs(driver, cat, is_first_call=(i == 0))
            offers = self.get_fly4free_category_offers(filtered_offers_divs, cat)
            for offer in offers:
                if offer not in self.cache:
                    all_fly4free_offers.append(offer)
                    self.cache.add(offer)
        logging.info(f"Found {len(offers)} fly4free offers")
        return all_fly4free_offers
