"""Record an AI visual transcription for the frozen image-heavy validation page."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'validation_blind_round2'
SAMPLE = 'collected_61b2572fd4c6cd0c.html'

# These blocks were transcribed by inspecting the downloaded images in order.
# They are a visual-review reference, not output from a locally installed OCR engine.
IMAGE_BLOCKS = [
    '中共中央就党的重要文件和国家重大方针政策听取各民主党派中央、全国工商联负责人和无党派人士的意见，是全过程人民民主特别是社会主义协商民主的重要体现。',
    '治国必先治党，强国必先强党。越是长期执政，越是承平日久，越是环境复杂，越要增强忧患意识、做到居安思危，持之以恒推进全面从严治党，确保中国共产党始终成为中国特色社会主义事业的坚强领导核心。',
    '要站在保持党的先进性和纯洁性、巩固党的执政地位、实现党的使命任务的战略高度，坚定信心、保持定力，切实把中国共产党治理好、建设强。',
    '解决党内存在的问题，首先要立足于中国共产党的自身力量，不断实现党的自我净化、自我完善、自我革新、自我提高；还要依靠人民的支持，主动接受人民监督，虚心听取群众批评，把人民群众的拥护和支持转化为持之以恒推进全面从严治党的强大动力。',
    '要坚持党性党风党纪一起抓，正风肃纪反腐相贯通，把管人、管事、管权有机结合起来，把锤炼党性、提高能力、净化生态统一起来。',
    '要坚持以上率下，从领导干部抓起严起，强化教育管理监督，引导党员、干部做到慎独慎初慎微、自重自省自警自励。',
    '希望各民主党派、工商联和无党派人士不忘初心，坚守中国共产党领导，不断夯实共同思想政治基础，积极建言资政，发挥好民主监督职能，做中国共产党的好参谋、好帮手、好同事。',
]


def run():
    sample_path = BATCH / 'samples' / SAMPLE
    snapshot = hashlib.sha256(sample_path.read_bytes()).hexdigest()
    inventory_path = BATCH / 'reports' / 'image_inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    images = [item for item in inventory['images'] if item['file'] == SAMPLE]
    if len(images) != len(IMAGE_BLOCKS):
        raise ValueError('Image inventory does not contain exactly seven images for this sample.')
    for item, block in zip(images, IMAGE_BLOCKS):
        item['ocr_status'] = 'ai_visual_reviewed'
        item['transcription'] = block
        item['review_note'] = '当前对话 AI 根据原图视觉检查转录；未由本机 OCR 引擎生成，建议人工抽查。'
    inventory['note'] = '图片按正文顺序登记；转录为当前对话 AI 视觉审核结果，不等同于本机 OCR 输出。'
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')

    report = {
        'reviewer': 'current-conversation AI',
        'method': '逐张查看下载图片，按页面顺序视觉转录；导语来自 DOM，图片块来自图像。',
        'sample': SAMPLE,
        'snapshot': snapshot,
        'status': 'visual_review_complete_ocr_engine_unavailable',
        'dom_intro': '8月21日，中共中央在中南海召开党外人士座谈会，就中共中央关于持之以恒推进全面从严治党若干重大问题的决定听取各民主党派中央、全国工商联负责人和无党派人士代表的意见建议。中共中央总书记习近平主持座谈会并发表重要讲话。他指出——',
        'body_blocks': [
            '8月21日，中共中央在中南海召开党外人士座谈会，就中共中央关于持之以恒推进全面从严治党若干重大问题的决定听取各民主党派中央、全国工商联负责人和无党派人士代表的意见建议。中共中央总书记习近平主持座谈会并发表重要讲话。他指出——',
            *IMAGE_BLOCKS,
        ],
        'note': '这是视觉审核参考答案，不是人工校对，也不是本机 OCR 引擎评测结果。',
    }
    destination = BATCH / 'reports' / 'ai_visual_review.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(destination)


if __name__ == '__main__':
    run()
