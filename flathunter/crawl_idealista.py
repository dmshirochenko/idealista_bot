"""Expose crawler for Idealista"""
import logging
import re

import requests
from bs4 import BeautifulSoup
from flathunter.abstract_crawler import Crawler
from random_user_agent.user_agent import UserAgent
from flathunter.oxylab_client import PushPullScraperAPIsClient


class CrawlIdealista(Crawler):
    """Implementation of Crawler interface for Idealista"""

    __log__ = logging.getLogger("flathunt")
    URL_PATTERN = re.compile(r"https://www\.idealista\.com")

    def __init__(self, config):
        self.config = config
        logging.getLogger("requests").setLevel(logging.WARNING)
        if config.scraper_api_enabled():
            capthca_scraper_api = config.get("oxylabs")
            self.scraper_api_key_user = capthca_scraper_api.get("user", "")
            self.scraper_api_password = capthca_scraper_api.get("password", "")
            # self.capthca_scraper_api_key = capthca_scraper_api.get('api_key', '')

    # pylint: disable=unused-argument
    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""

        if self.config.use_proxy():
            return self.get_soup_with_proxy(search_url)

        return self.get_soup_from_url(
            search_url,
            capthca_scraper_api_user=self.scraper_api_key_user,
            capthca_scraper_api_password=self.scraper_api_password,
        )

    def get_soup_from_url(
        self,
        url,
        driver=None,
        captcha_api_key=None,
        capthca_scraper_api_user=None,
        capthca_scraper_api_password=None,
        checkbox=None,
        afterlogin_string=None,
    ):

        try:
            # Check if Oxylabs job id availabe in self.config
            job_id = self.config.get("oxylabs_job_id", None)
            if job_id:
                self.__log__.info(f"Using existing Oxylabs job ID: {job_id}")
                # Use the existing job ID to fetch results
                oxylabs_client = PushPullScraperAPIsClient(self.scraper_api_key_user, self.scraper_api_password)
                job_result = oxylabs_client.wait_for_and_get_job_results(job_id)
                return BeautifulSoup(job_result["results"][0]["content"], "html.parser")
            else:
                # If no job ID is available, fall back to direct fetching
                return self.get_soup_from_url_direct_fetching(
                    url,
                    capthca_scraper_api_user=capthca_scraper_api_user,
                    capthca_scraper_api_password=capthca_scraper_api_password,
                )

        except Exception as e:
            self.__log__.exception("Failed to fetch or parse content from URL: %s", url)
            return BeautifulSoup("", "html.parser")  # Safe fallback

    def get_soup_from_url_direct_fetching(
        self,
        url,
        driver=None,
        captcha_api_key=None,
        capthca_scraper_api_user=None,
        capthca_scraper_api_password=None,
        checkbox=None,
        afterlogin_string=None,
    ):
        """Creates a Soup object from the HTML at the provided URL"""

        # Structure payload.
        payload = {"url": url, "render": ""}

        try:
            resp = requests.post(
                "https://realtime.oxylabs.io/v1/queries",
                auth=(capthca_scraper_api_user, capthca_scraper_api_password),
                json=payload,
            )
            resp.raise_for_status()

            data = resp.json()
            results = data.get("results", [])

            if not results:
                self.__log__.error("No results in response")

            result = results[0]
            status_code = result.get("status_code")
            content = result.get("content")

            if status_code not in [200] or not content:
                self.__log__.error("Unexpected response (%s)", status_code)
                return BeautifulSoup("", "html.parser")  # Safe fallback

            return BeautifulSoup(content, "html.parser")

        except Exception as e:
            self.__log__.exception("Failed to fetch or parse content from URL: %s", url)
            return BeautifulSoup("", "html.parser")  # Safe fallback

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = list()

        findings = soup.find_all("article", {"class": "item"})

        base_url = "https://www.idealista.com"
        for row in findings:
            title_row = row.find("a", {"class": "item-link"})
            title = title_row.text.strip()
            url = base_url + title_row["href"]
            picture_element = row.find("picture", {"class": "item-multimedia"})
            if "no-pictures" not in picture_element.get("class"):
                image = ""
            else:
                print(picture_element)
                image = picture_element.find("img")["src"]

            # It's possible that not all three fields are present
            detail_items = row.find_all("span", {"class": "item-detail"})
            rooms = detail_items[0].text.strip() if (len(detail_items) >= 1) else ""
            size = detail_items[1].text.strip() if (len(detail_items) >= 2) else ""
            floor = detail_items[2].text.strip() if (len(detail_items) >= 3) else ""
            price = row.find("span", {"class": "item-price"}).text.strip().split("/")[0]

            details_title = ("%s - %s" % (title, floor)) if (len(floor) > 0) else title

            details = {
                "id": int(row.get("data-element-id")),
                "image": image,
                "url": url,
                "title": details_title,
                "price": price,
                "size": size,
                "rooms": rooms,
                "address": title,
                "crawler": self.get_name(),
            }

            entries.append(details)

        # self.__log__.debug("extracted: {}".format(entries))

        return entries
