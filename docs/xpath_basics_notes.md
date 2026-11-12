# XPath 基础学习笔记

记录日期：2026-11-03。配合 `xpath_practice.py` 和新浪模板适配练习阅读。以下示例采用 Python lxml 支持的 XPath 1.0。

## 1. div 在网页和 XPath 中的作用

`div` 是 HTML 标签，常用来把内容组织成区域。正文、导航、广告、侧栏都可能使用 div，因此不能仅凭标签名判断它是不是正文。

```html
<div class="article" id="artibody">
    <p>第一段正文。</p>
    <p>第二段正文。</p>
    <p class="article-editor">责任编辑：张三</p>
</div>
```

这里外层 div 是容器，里面有三个 p 元素。

```xpath
//div[@id='artibody']
```

表示在整个文档中查找 id 属性等于 artibody 的 div。XPath 不知道 artibody 代表正文；这是我们查看 DOM 和页面范围后做出的判断。选对容器后，容器内部仍可能混有编辑信息等非正文内容。

## 2. 常用规则速查

| 写法 | 含义 | 示例 |
|---|---|---|
| 标签名 | 按元素类型选择 | p、div、h1 |
| / | 选择下一层直接子元素；开头的 / 从文档根节点出发 | /html/body |
| // | 跨层级查找；开头的 // 从整个文档查找 | //h1 |
| . | 当前节点 | ./p |
| .. | 当前节点的父节点 | .. |
| @ | 属性 | @id、@class |
| [...] | 筛选条件 | //div[@id='artibody'] |
| * | 任意元素标签 | //*[@id='artibody'] |
| &#124; | 合并两组节点，去重并按文档顺序返回 | ./p &#124; ./div[@class='pictext'] |
| [数字] | 按位置选择，位置从 1 开始 | ./p[1] |
| not(...) | 排除符合条件的节点 | ./p[not(@class='article-editor')] |
| contains(a, b) | 判断字符串 a 是否包含 b | //div[contains(@class, 'article')] |

位置筛选注意：`//p[1]` 选择各父节点下的第一个 p；`(//p)[1]` 才是整份文档的第一个 p。`./p[1]` 是当前节点的第一个直接子 p。Python 列表索引则从 0 开始。

## 3. ./p、.//p 与 //p 的区别

假设 Python 中 container 已经指向正文容器：

```python
container.xpath('./p')    # 直接子级 p
container.xpath('.//p')   # 容器内所有层级的 p
container.xpath('//p')    # 整个文档中的 p，可能选到正文之外
```

想限定在当前容器内，通常要保留前面的点号。跨层级选择可能找回嵌套正文，也可能混入嵌套广告，不能简单认为越广越好。

```html
<div id="artibody">
    <p>第一段</p>
    <div class="section">
        <p>嵌套段落</p>
    </div>
    <div class="pictext">图片说明</div>
</div>
```

在 artibody 容器上执行：

| XPath | 选中的元素 |
|---|---|
| ./p | 第一段的 p |
| .//p | 第一段、嵌套段落的 p |
| ./div | section 容器、图片说明容器 |
| ./div[@class='pictext'] | 图片说明容器 |
| ./p &#124; ./div[@class='pictext'] | 第一段和图片说明，保持文档顺序 |

## 4. id 和 class 的匹配

### id 精确匹配

```xpath
//div[@id='artibody']
```

要求标签为 div 且 id 完全相等。若不限定标签，可写 `//*[@id='artibody']`。规范 HTML 中 id 应唯一，但实际页面可能不规范，仍需检查匹配数量。

### class 可能包含多个类名

```html
<p class="article-editor">责任编辑：张三</p>
<p class="article-editor muted">责任编辑：张三</p>
```

`./p[@class='article-editor']` 只匹配第一种，因为它要求整个属性完全相等。

`contains(@class, 'article-editor')` 是子串匹配，也会匹配 article-editor-extra，适合临时查找，但需要注意误匹配。

按独立类名匹配的常用 XPath 1.0 写法：

```xpath
./p[contains(concat(' ', normalize-space(@class), ' '), ' article-editor ')]
```

- normalize-space：去掉首尾空白，并把连续空白合并成一个空格。
- concat：在类名字符串两端补空格。
- contains：检查带空格边界的完整类名。

排除责任编辑节点：

```xpath
./p[not(contains(concat(' ', normalize-space(@class), ' '), ' article-editor '))]
```

这种方法利用节点结构，避免直接删除所有包含“编辑”二字的正常正文。它依赖当前网站类名约定，换模板后仍需要验证。

## 5. 选择元素与读取文字是两个步骤

```python
nodes = container.xpath('./p')
if nodes:
    text = nodes[0].text_content()
    text = ' '.join(text.split())
```

xpath 先返回 p 元素列表；text_content() 再读取元素及后代中的文字。split/join 用于归一化空白，不负责判断文字是否正文。

例如：

```html
<p>这是一段<strong>重要</strong>正文。</p>
```

text_content() 得到“这是一段重要正文。”。

```xpath
./p/text()
```

只读取 p 的直接文本节点，结果不包含 strong 中的“重要”。因此当前练习先选元素，再读取其全部文字。

注意：text_content() 不模拟浏览器可见性，也不会自动排除隐藏文字或广告。没有文字的节点还可能包含 img；“文本为空”不等于“没有内容”。

## 6. 浏览器中的定位练习

打开新浪练习页，在浏览器开发者工具的 Elements／元素面板按 Ctrl+F，依次搜索：

```xpath
//div[@id='artibody']
```

```xpath
//div[@id='artibody']/p
```

```xpath
//div[@id='artibody']/p[1]
```

```xpath
//div[@id='artibody']/p[contains(@class, 'article-editor')]
```

依次观察：正文容器、直接子段落、第一个段落、责任编辑段落。记录匹配数量并观察高亮范围。若开发者工具没有打开，可在网页正文上右键选择“检查”。

## 7. 和当前项目的对应关系

- title_xpath：查找标题节点，例如 //h1。
- container_xpath：确定正文查询范围，例如 //div[@id='artibody']。
- block_xpath：在容器内选择内容块，例如 ./p。
- 图片说明可能使用 div.pictext，因此只选 p 会漏掉图说。
- paragraph 表示按结构识别出的段落，不保证该段语义上一定属于正文；责任编辑等内容也可能放在 p 中。
- 匹配数量、文字差异、DOM 结构检查可以发现问题线索；内容保留范围仍需明确标准和审查证据。

学习验收：能解释“在哪个节点上运行 XPath、选择了哪些层级、用了什么属性、可能漏掉什么或混入什么”。
