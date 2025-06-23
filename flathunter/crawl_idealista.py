"""Expose crawler for Idealista"""
import logging
import re

import requests
from bs4 import BeautifulSoup
from flathunter.abstract_crawler import Crawler
from random_user_agent.user_agent import UserAgent

class CrawlIdealista(Crawler):
    """Implementation of Crawler interface for Idealista"""

    __log__ = logging.getLogger('flathunt')
    URL_PATTERN = re.compile(r'https://www\.idealista\.com')

    def __init__(self, config):
        self.config = config
        logging.getLogger("requests").setLevel(logging.WARNING)
        if config.scraper_api_enabled():
            capthca_scraper_api = config.get('oxylabs')
            self.scraper_api_key_user = capthca_scraper_api.get('user', '')
            self.scraper_api_password = capthca_scraper_api.get('password', '')
            #self.capthca_scraper_api_key = capthca_scraper_api.get('api_key', '')

    # pylint: disable=unused-argument
    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""

        if (self.config.use_proxy()):
            return self.get_soup_with_proxy(search_url)

        return self.get_soup_from_url(search_url, capthca_scraper_api_user=self.scraper_api_key_user, capthca_scraper_api_password=self.scraper_api_password)


    def get_soup_from_url(self, url, driver=None, captcha_api_key=None, capthca_scraper_api_user=None, capthca_scraper_api_password=None, checkbox=None, afterlogin_string=None):
        """Creates a Soup object from the HTML at the provided URL"""

        # self.rotate_user_agent() #not used with scraperapi or brightdata api

        # headers = {"Authorization": captcha_api_key, "Content-Type": "application/json"}

        # payload = {'api_key': captcha_api_key, 'url': url} scraperapi
        # resp = requests.get('http://api.scraperapi.com', headers=self.HEADERS, params=payload) scraperapi

        # payload = {"zone": "web_unlocker1", 'url': url, "format": "raw"}
        # resp = requests.post("https://api.brightdata.com/request?",json=payload, headers=headers)

        # Structure payload.
        payload = {
            'url': url
        }

        # Get response.
        resp = requests.request(
            'POST',
            'https://realtime.oxylabs.io/v1/queries',
            auth=(capthca_scraper_api_user, capthca_scraper_api_password), #Your credentials go here
            json=payload,
        )

        data = resp.json()

        if data["results"][0]["status_code"] != 200 and data["results"][0]["status_code"] != 405:
            self.__log__.error("Got response (%i): %s", resp.status_code, resp.content)
        
        return BeautifulSoup(data["results"][0]["content"], 'html.parser')

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = list()

        findings = soup.find_all('article', {"class": "item"})

        base_url = 'https://www.idealista.com'
        for row in findings:
            title_row = row.find('a', {"class": "item-link"})
            title = title_row.text.strip()
            url = base_url + title_row['href']
            picture_element = row.find('picture', {"class": "item-multimedia"})
            if "no-pictures" not in picture_element.get("class"):
                image = ""
            else:
                print(picture_element)
                image = picture_element.find('img')['src']

            # It's possible that not all three fields are present
            detail_items = row.find_all("span", {"class": "item-detail"})
            rooms = detail_items[0].text.strip() if (len(detail_items) >= 1) else ""
            size = detail_items[1].text.strip() if (len(detail_items) >= 2) else ""
            floor = detail_items[2].text.strip() if (len(detail_items) >= 3) else ""
            price = row.find("span", {"class": "item-price"}).text.strip().split("/")[0]


            details_title = ("%s - %s" % (title, floor)) if (len(floor) > 0) else title

            details = {
                'id': int(row.get("data-element-id")),
                'image': image,
                'url': url,
                'title': details_title,
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': title,
                'crawler': self.get_name()
            }

            entries.append(details)

        self.__log__.debug('extracted: {}'.format(entries))

        return entries
