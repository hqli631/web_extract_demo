"""Generated reusable XPath extractor; trusted engine interprets data."""
import json
from project2_engine import extract as _engine
RULES = json.loads('{"title_xpath": "//article[contains(@class, \'product_page\')]//h1", "container_xpath": "//article[contains(@class, \'product_page\')]", "block_xpath": ".//div[@id=\'product_description\'] | .//p[not(contains(@class, \'price_color\')) and not(contains(@class, \'instock availability\')) and not(contains(@class, \'star-rating\'))] | .//div[contains(@class, \'sub-header\')][.//h2[contains(text(), \'Product Information\')]] | .//table[contains(@class, \'table-striped\')]", "exclude_xpath": ".//div[@id=\'product_gallery\'] | .//div[contains(@class, \'alert-warning\')] | .//section[@id=\'reviews\'] | .//div[contains(@class, \'sub-header\')][.//h2[contains(text(), \'Products you recently viewed\')]] | .//ul[contains(@class, \'row\')]", "metadata_xpath": "", "metadata_fields": {}}')
def extract(data):
    return _engine(RULES, data)
