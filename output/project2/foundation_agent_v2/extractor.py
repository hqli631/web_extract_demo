"""Generated reusable XPath extractor; trusted engine interprets data."""
import json
from project2_engine import extract as _engine
RULES = json.loads('{"title_xpath": "//article/header//h1", "container_xpath": "//article/div[1]", "block_xpath": ".//p | .//h2 | .//h3 | .//li[not(.//p)] | .//table | .//figcaption | .//pre", "exclude_xpath": "", "metadata_xpath": "//article/header//time | //article/header//a[contains(@href, \\"/authors/\\")]"}')
def extract(data):
    return _engine(RULES, data)
