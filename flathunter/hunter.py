"""Default Flathunter implementation for the command line"""
import logging
from itertools import chain

from flathunter.config import Config
from flathunter.filter import Filter
from flathunter.processor import ProcessorChain


class Hunter:
    """Hunter class - basic methods for crawling and processing / filtering exposes"""

    __log__ = logging.getLogger("flathunt")

    def __init__(self, config, id_watch, already_seen_filter=None):
        self.config = config
        if not isinstance(self.config, Config):
            raise Exception("Invalid config for hunter - should be a 'Config' object")
        self.id_watch = id_watch
        self.already_seen_filter = already_seen_filter

    def crawl_for_exposes(self, max_pages=None):
        """Trigger a new crawl of the configured URLs"""
        return chain(
            *[
                searcher.crawl(url, max_pages)
                for searcher in self.config.searchers()
                for url in self.config.get("urls", list())
            ]
        )

    def hunt_flats(self, max_pages=None):
        """Crawl, process and filter exposes"""

        # We build a filter set that only contains the already_seen_filter.
        # This ensures the processor chain receives the correct object type.
        filter_builder = Filter.builder()
        if self.already_seen_filter:
            filter_builder.add_filter(self.already_seen_filter)
        filter_set = filter_builder.build()

        processor_chain = (
            ProcessorChain.builder(self.config)
            .apply_filter(filter_set)
            .save_all_exposes(self.id_watch)
            .send_messages()
            .mark_as_processed(self.id_watch)
            .build()
        )

        result = []
        # We need to iterate over this list to force the evaluation of the pipeline

        for expose in processor_chain.process(self.crawl_for_exposes(max_pages)):
            self.__log__.info("New offer: %s", expose["title"])
            result.append(expose)

        return result
