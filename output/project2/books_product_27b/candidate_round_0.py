"""Generated reusable XPath extractor; trusted engine interprets data."""
import json
from project2_engine import extract as _engine
RULES = json.loads('{"title_xpath": "//article[@class=\'product_page\']/div[1]/div[2]/h1", "container_xpath": "//article[@class=\'product_page\']", "block_xpath": "div[1]/div[2]/p | div[2] | p | div[3] | table", "exclude_xpath": "div[@class=\'alert alert-warning\'] | section | div[4] | ul", "metadata_xpath": "", "metadata_fields": {}}')
def extract(data):
    return _engine(RULES, data)
