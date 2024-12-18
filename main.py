import logging
import os
import platform
import time

import schedule
import yagmail
from dotenv import load_dotenv
from jinja2 import Template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from fly_4_free import Fly4Free
from lastminuter import LastMinuter
from offer import Offer
from wakacyjni_piraci import WakacyjniPiraci


def get_driver() -> webdriver.Chrome:
    system = platform.system()
    if system not in {"Windows", "Linux"}:
        raise ValueError("This driver only works on Windows and Linux systems.")

    browser = 'chrome' if system == "Linux" else 'edge'

    options = webdriver.ChromeOptions() if browser == 'chrome' else webdriver.EdgeOptions()
    options.add_argument("window-size=1400,1080")
    options.add_argument("--disk-cache-size=10485760")
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--log-level=3')
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins-discovery")

    if browser == 'chrome':
        options.binary_location = "/usr/bin/chromium-browser"
    # Disable loading images for better performance
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/58.0.3029.110 Safari/2b7c7"
    )
    if browser == "chrome":
        return webdriver.Chrome(options, Service(executable_path="/usr/bin/chromedriver"))
    else:
        return webdriver.Chrome(options=options)


def render_html(offers: list[Offer]) -> str:
    with open('template.html', 'rt', encoding='utf-8') as f:
        html_template = f.read()
    template = Template(html_template)
    return template.render(offers=offers)


def send_mail(html_content: str) -> None:
    load_dotenv()
    email_subject = 'Oferty wakacje'
    yag = yagmail.SMTP(os.getenv('SRC_MAIL'), os.getenv('SRC_PWD'), port=587, smtp_starttls=True, smtp_ssl=False)
    yag.send(to=os.getenv('DST_MAIL'), subject=email_subject, contents=(html_content, 'text/html'))
    logging.debug("Mail sended")


def main():
    driver = get_driver()
    lastminuter_offers = LastMinuter().get_offers(driver)
    piraci_offers = WakacyjniPiraci().get_offers(driver)
    fly_4_free_offers = Fly4Free().get_offers(driver)
    offers = [*lastminuter_offers, *piraci_offers, *fly_4_free_offers]

    driver.close()

    html_content = render_html(offers)
    logging.debug("Rendered html")
    with open('holidays.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    send_mail(html_content)


VERIFY_SSL = True
if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - Line: %(lineno)d - %(filename)s - %(funcName)s() - %(message)s',
        level=logging.DEBUG
    )
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    schedule.every().day.at("12:00").do(main)
    # main()
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logging.exception("An error occurred:")
            print(e)
            time.sleep(60 * 60)
        time.sleep(1)
