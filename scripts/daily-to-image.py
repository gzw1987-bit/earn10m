"""将 AI 日报 Markdown 转成适合社交媒体分享的 HTML 长图"""
import sys
import re
import os

def md_to_share_html(md_path, html_path):
    with open(md_path, 'r') as f:
        content = f.read()

    # 提取日期
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', content)
    date = date_match.group(1) if date_match else ''

    # 解析 sections
    sections = []
    current_section = None
    current_items = []

    for line in content.split('\n'):
        line = line.rstrip()
        if line.startswith('## '):
            if current_section:
                sections.append((current_section, '\n'.join(current_items)))
            current_section = line[3:].strip()
            current_items = []
        elif line.startswith('# '):
            continue  # skip title
        elif line.startswith('---'):
            continue
        elif line.startswith('*') and line.endswith('*') and '日报' in line:
            continue  # skip footer
        elif line.startswith('Sources:') or line.startswith('- ['):
            continue  # skip source links
        else:
            if current_section:
                current_items.append(line)

    if current_section:
        sections.append((current_section, '\n'.join(current_items)))

    # 生成 section HTML
    section_html = ''
    section_icons = {
        '今日最重要的事': '🔥',
        '今日AI赚钱情报': '💰',
        '值得关注的信号': '📡',
        '一句话总结': '💎',
    }
    section_colors = {
        '今日最重要的事': '#dc2626',
        '今日AI赚钱情报': '#f59e0b',
        '值得关注的信号': '#818cf8',
        '一句话总结': '#34d399',
    }

    for title, body in sections:
        icon = section_icons.get(title, '📌')
        color = section_colors.get(title, '#818cf8')

        # 处理正文：加粗、编号等
        body_html = ''
        paragraphs = body.strip().split('\n\n')

        for para in paragraphs:
            if not para.strip():
                continue
            lines = para.strip().split('\n')
            para_text = ' '.join(lines)

            # 处理编号列表
            if re.match(r'^\d+\.', para_text):
                items = re.split(r'(?=\d+\.\s)', para_text)
                for item in items:
                    item = item.strip()
                    if not item:
                        continue
                    # 处理加粗
                    item = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#fafafa;">\1</strong>', item)
                    body_html += f'<div style="padding:16px 0; border-bottom:1px solid #1a1a2e; font-size:24px; color:#a3a3a3; line-height:1.8;">{item}</div>'
            else:
                para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#fafafa;">\1</strong>', para_text)
                body_html += f'<div style="padding:16px 0; font-size:24px; color:#a3a3a3; line-height:1.8;">{para_text}</div>'

        if title == '一句话总结':
            # 特殊样式
            body_clean = re.sub(r'\*\*(.+?)\*\*', r'\1', body.strip())
            section_html += f'''
            <div style="margin-top:32px; background:rgba(52,211,153,.06); border:1px solid rgba(52,211,153,.15); border-radius:16px; padding:32px;">
                <div style="font-size:16px; color:{color}; font-weight:700; margin-bottom:12px;">{icon} {title}</div>
                <div style="font-size:26px; color:#e5e5e5; line-height:1.8; font-weight:500;">{body_clean}</div>
            </div>'''
        else:
            section_html += f'''
            <div style="margin-top:40px;">
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                    <span style="font-size:20px;">{icon}</span>
                    <span style="font-size:28px; font-weight:900; color:{color};">{title}</span>
                </div>
                <div style="background:#0d0d14; border:1px solid #1e1e2e; border-radius:16px; padding:24px;">
                    {body_html}
                </div>
            </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#000; font-family:'Noto Sans SC',sans-serif; color:#fafafa; display:flex; justify-content:center; }}
  .page {{ width:1080px; background:#08080c; padding:60px 64px 80px; }}
</style>
</head>
<body>
<div class="page">
  <!-- 头部 -->
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div style="display:flex; align-items:center; gap:12px;">
      <span style="background:rgba(99,102,241,.12); border:1px solid rgba(99,102,241,.3); color:#818cf8; padding:8px 20px; border-radius:100px; font-size:20px; font-weight:700; letter-spacing:3px;">AI日报</span>
      <span style="background:rgba(52,211,153,.1); border:1px solid rgba(52,211,153,.2); color:#34d399; padding:8px 16px; border-radius:100px; font-size:18px; font-weight:600;">OPC × AI</span>
    </div>
    <span style="font-size:24px; color:#333; font-family:'Courier New',monospace;">{date}</span>
  </div>

  <div style="margin-top:24px; font-size:44px; font-weight:900;">
    AI日报 · <span style="color:#818cf8;">{date}</span>
  </div>

  {section_html}

  <!-- 底部 -->
  <div style="margin-top:48px; padding-top:24px; border-top:1px solid #1e1e2e; text-align:center;">
    <div style="font-size:20px; color:#333; line-height:2;">
      @年赚千万真实记录 · OPC一人公司 × AI<br>
      <span style="color:#444;">每天7点更新 · 关注我获取每日AI情报</span>
    </div>
  </div>
</div>
</body>
</html>'''

    with open(html_path, 'w') as f:
        f.write(html)
    print(f'HTML generated: {html_path}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python3 daily-to-image.py <input.md> <output.html>')
        sys.exit(1)
    md_to_share_html(sys.argv[1], sys.argv[2])
