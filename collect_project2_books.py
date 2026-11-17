"""Collect 10 deterministic product pages from the public Books to Scrape sandbox."""
from datetime import datetime, timezone
import hashlib
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from lxml import html

ROOT=Path(__file__).resolve().parent
BASE='http://books.toscrape.com/'
OUT=ROOT/'data/project2/books_product_v1'
UA='WebExtractLearningDemo/1.0'
OPENER=urllib.request.build_opener()

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':UA})
    with OPENER.open(request,timeout=45) as response:
        if urllib.parse.urlsplit(response.url).netloc!='books.toscrape.com':
            raise ValueError('Unexpected redirect')
        return response.read(),response.url,response.status

def main():
    global OPENER
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy',help='Optional local HTTP proxy, e.g. http://127.0.0.1:7897')
    args=parser.parse_args()
    if args.proxy:
        OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({'http':args.proxy,'https':args.proxy}))
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'manifest.json').exists():
        raise SystemExit('Collection already frozen; use existing snapshots')
    receipt={'site':BASE,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'assets':[]}
    robots=urllib.robotparser.RobotFileParser()
    try:
        raw,_,status=fetch(BASE+'robots.txt')
        (OUT/'robots.txt').write_bytes(raw)
        robots.parse(raw.decode('utf8',errors='replace').splitlines())
        receipt['robots_status']=status
    except urllib.error.HTTPError as exc:
        if exc.code!=404:
            raise
        receipt.update(robots_status=404,robots_policy='No robots.txt returned; public scraping practice site; low-rate fixed 10-page batch')
        robots=None
    index,_,_=fetch(BASE)
    (OUT/'discovery.html').write_bytes(index)
    doc=html.document_fromstring(index)
    urls=list(dict.fromkeys(urllib.parse.urljoin(BASE,v) for v in doc.xpath('//article[contains(@class,"product_pod")]//h3/a/@href')))[:10]
    if len(urls)!=10:
        raise ValueError('Discovery did not yield 10 product detail pages')
    roles=['generation','final_holdout','development_feedback','final_holdout','generation',
           'final_holdout','development_feedback','final_holdout','generation','final_holdout']
    pages=[];asset_urls=set()
    # Role assignment is decided from deterministic positions before body review.
    for i,(url,role) in enumerate(zip(urls,roles),1):
        if robots and not robots.can_fetch(UA,url):
            raise ValueError('Robots disallows target')
        time.sleep(0.6)
        raw,resolved,status=fetch(url)
        relative=Path(urllib.parse.urlsplit(url).path.lstrip('/'))
        target=OUT/'site'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(raw)
        # Asset discovery is mechanical; no held-out text is summarized or reviewed.
        tree=html.document_fromstring(raw)
        for value in tree.xpath('//link[@rel="stylesheet"]/@href | //article//img/@src'):
            asset=urllib.parse.urljoin(url,value)
            if urllib.parse.urlsplit(asset).netloc=='books.toscrape.com':
                asset_urls.add(asset)
        page=dict(id=f'book_product_{i:02}',path=target.relative_to(ROOT).as_posix(),url=url,final_url=resolved,
                  role=role,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),http_status=status,
                  source_exposure='new_product_layout_task; heldout excluded from prompt and repair; not a pretraining claim')
        pages.append(page)
        print(page['id'],role,status,len(raw),flush=True)
    for url in sorted(asset_urls):
        time.sleep(0.3)
        try:
            raw,_,status=fetch(url)
            target=OUT/'site'/urllib.parse.urlsplit(url).path.lstrip('/')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(raw)
            receipt['assets'].append(dict(url=url,path=target.relative_to(ROOT).as_posix(),bytes=len(raw),status=status))
        except Exception as exc:
            receipt['assets'].append(dict(url=url,error=type(exc).__name__))
    task=dict(schema_version=2,task_id='books-product-v1',scope='10 new book product detail pages; 3 generation, 2 development, 5 final holdout; same product layout, different from Python release blogs.',
              summary_scope_xpath='//article[contains(concat(" ",normalize-space(@class)," ")," product_page ")]',
              evaluation_scope_xpath='//article[contains(concat(" ",normalize-space(@class)," ")," product_page ")]',
              prompt='Extract book product content: title, ordered description, product facts table, price and stock text. Keep meaningful product headings. Do not invent author/date when absent. Cart controls and global navigation are UI rather than book description. Return shared XPath JSON rules, not page-specific answers. No OCR is provided.',
              retrieved_at_utc=receipt['retrieved_at_utc'],pages=pages)
    (OUT/'collection_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    (OUT/'manifest.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf8')
    (ROOT/'config/project2_books_product_v1.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf8')
    print('Frozen 10-page task; generation/dev only may enter Agent input')

if __name__=='__main__':
    main()
