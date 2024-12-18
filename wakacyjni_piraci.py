import logging
import re
from pathlib import Path

from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from offer import Offer
from scrapper_base import ScrapperBase


class WakacyjniPiraci(ScrapperBase):
    def __init__(self):
        super().__init__(cache_path=Path('wakacyjni_piraci_cache.pkl.zstd'))
        self.url = 'https://www.wakacyjnipiraci.pl'
        self.cookies_locator = (By.XPATH, "//button[normalize-space()='Akceptuj wszystko']")
        self.offer_locator = (By.XPATH, "//div[starts-with(@style, 'order')]")
        self.a_locator = (By.TAG_NAME, 'a')
        self.specific_link_locator = (By.XPATH, "//div[@class='hp__sc-1v8qbhd-0 ccLcxQ']/a")

    def get_wakacyjni_piraci_divs(self, driver: webdriver.Chrome, wait: WebDriverWait) -> list[WebElement]:
        driver.get(self.url)
        button = wait.until(EC.presence_of_element_located(self.cookies_locator))
        # Accept cookies
        button.click()
        return wait.until(EC.presence_of_all_elements_located(self.offer_locator))

    def create_wakacyjni_piraci_offers(
            self, filtered_divs: list[WebElement], driver: webdriver.Chrome, wait: WebDriverWait
    ) -> list[Offer]:
        wakacyjni_piraci_offers = []
        for d in filtered_divs:
            try:
                a = d.find_element(*self.a_locator)
            except Exception:
                continue
            href = a.get_attribute('href')
            splitted_text = d.text.split('\n')
            if 'inclusive' not in d.text.lower():
                continue
            # remove publish date
            indexes_to_ignore = set()
            price_str = main_category = sub_category = ''
            for s in splitted_text:
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

            # Open the link with the driver and find the specific link in the div
            driver.get(href)
            try:
                specific_link_element = wait.until(
                    EC.presence_of_element_located(self.specific_link_locator)
                )
                specific_link = specific_link_element.get_attribute('href')
            except TimeoutException:
                specific_link = href
            wakacyjni_piraci_offers.append(
                Offer(specific_link, title, price_str, f'{main_category} {sub_category}'.strip())
            )

        return wakacyjni_piraci_offers

    def get_offers(self, driver: webdriver.Chrome) -> list[Offer]:
        wait = WebDriverWait(driver, 20)
        divs = self.get_wakacyjni_piraci_divs(driver, wait)

        # 18 elements on page -> others are trash
        filtered_divs = [div for div in divs[:18] if re.search(r'(Za|Od)', div.text)]
        if not filtered_divs:
            print('Wakacyjni piraci - nic nie znaleziono')
        offers = self.create_wakacyjni_piraci_offers(filtered_divs, driver, wait)
        offers = [offer for offer in offers if offer not in self.cache]
        for offer in offers:
            self.cache.add(offer)
        logging.info(f"Found {len(offers)} wakacyjnipiraci offers")
        return offers
