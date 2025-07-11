"""Expose crawler for Subito"""
import logging
import re
import json

from flathunter.abstract_crawler import Crawler


class CrawlSubito(Crawler):
    """Implementation of Crawler interface for Subito"""

    __log__ = logging.getLogger("flathunt")
    URL_PATTERN = re.compile(r"https://www\.subito\.it")

    def __init__(self, config):
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.config = config

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = list()

        # as of today, subito provides a useful JSON that represents the state
        # of the search. Neat! We don't have to do much.
        findings_json = soup.find("script", {"id": "__NEXT_DATA__"}).text.strip()
        findings = json.loads(findings_json)["props"]["state"]["items"]["list"]

        for row in findings:
            id = row["item"]["urn"]
            title = row["item"]["subject"]

            # some advertisements sneak in their search for apartments into
            # the rent section, so we skip them
            if re.match(r"cerco", title, re.IGNORECASE):
                continue
            url = row["item"]["urls"]["default"]
            images = row["item"]["images"]

            # we get the first image available. According to the structure
            # there is the possibility to have different image sizes (small, slider,
            # medium...), but we will just get the first one if available.
            image = images[4]["scale"][4]["secureuri"] if len(images) > 4 else ""

            features = row["item"]["features"]

            price = features["/price"]["values"][0]["key"] if "/price" in features else "?"
            rooms = features["/room"]["values"][0]["key"] if "/room" in features else "?"
            size = features["/size"]["values"][0]["key"] if "/size" in features else "?"

            # Unfortunately, Subito does not give the full address, so we'll just have to work
            # with what we got and be happy with the address
            geo = row["item"]["geo"]
            address = "%s, %s, %s" % (
                geo["town"]["value"] if geo["town"] else "",
                geo["city"]["shortName"] if geo["city"] else "",
                geo["region"]["value"] if geo["region"] else "",
            )

            details = {
                "id": re.sub(r"[^0-9]", "", id),
                # the image is correct... however for some reason they don't show up
                # in telegram's thumbnail
                "image": image,
                "url": url,
                "title": title,
                "price": price,
                "size": size,
                "rooms": rooms,
                "address": address,
                "crawler": self.get_name(),
            }

            entries.append(details)

        self.__log__.debug("extracted: {}".format(entries))

        return entries
