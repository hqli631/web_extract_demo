"""Stable node identities shared by extraction and the frozen review copy."""
from bs4 import BeautifulSoup


def marked_source(source):
    soup = BeautifulSoup(source, 'html.parser')
    for index, node in enumerate(soup.find_all(True)):
        node['data-review-node'] = str(index)
    return soup
