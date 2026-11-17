"""Fixed worker process: XPath data only, no model Python execution."""
import json
import sys
import base64
from project2_engine import extract, structural_feedback

def main():
    request = json.load(sys.stdin)
    data = base64.b64decode(request['html_base64'], validate=True)
    result = extract(request['rules'], data)
    print(json.dumps({'result':result, 'issues':structural_feedback(result,data,request.get('scope_xpath'))},ensure_ascii=False))

if __name__ == '__main__':
    main()
