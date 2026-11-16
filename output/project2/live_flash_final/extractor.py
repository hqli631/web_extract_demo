"""Generated reusable XPath extractor; trusted engine interprets data."""
import json
from project2_engine import extract as _engine
RULES = json.loads('{"title_xpath": "/html/body/main/div/article/header/div[1]/div/h1", "container_xpath": "/html/body/main/div/article/div[@class=\'animate-fade-up stagger-1\']", "block_xpath": "./p | ./h2 | ./h3 | ./ul | ./ol | ./blockquote | ./pre | ./table | ./figure", "exclude_xpath": "", "metadata_xpath": "/html/body/main/div/article/header/div[2]/a | /html/body/main/div/article/header/div[2]/time"}')
def extract(data):
    return _engine(RULES, data)
