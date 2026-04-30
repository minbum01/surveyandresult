import re
import os

def parse_markdown(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return {}
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    sections = {}
    current_section = None
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('## '):
            current_section = line[3:].strip()
            sections[current_section] = []
        elif ' × ' in line and '(' in line and ')' in line:
            # Match pattern: 상황 × 직렬 × 베이스 (숫자)
            parts = line.split(' × ')
            if len(parts) >= 3:
                # The last part contains the base and the count
                last_part = parts[-1]
                match = re.search(r'(.*)\s+\((\d+)\)', last_part)
                if match:
                    base = match.group(1).strip()
                    count = int(match.group(2))
                    job = parts[1].strip()
                    sections[current_section].append({
                        'job': job,
                        'base': base,
                        'count': count
                    })
    
    return sections

def generate_html(data, output_path):
    total_cases = sum(len(v) for v in data.values())
    total_reviews = sum(sum(item['count'] for item in v) for v in data.values())
    total_categories = len(data)

    html_content = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>동일상황 화이팅멘트 케이스 보고서</title>
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
        
        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 40px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        h1 {{ margin: 0; font-size: 2.5em; letter-spacing: -1px; }}
        header p {{ margin-top: 10px; opacity: 0.9; font-weight: 300; }}
        
        .summary {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            display: flex;
            justify-content: space-around;
            text-align: center;
        }}
        .summary-item {{ flex: 1; border-right: 1px solid #eee; }}
        .summary-item:last-child {{ border-right: none; }}
        .summary-value {{ font-size: 2.2em; font-weight: 800; color: #764ba2; margin-bottom: 5px; }}
        .summary-label {{ font-size: 0.9em; color: #868e96; font-weight: 600; }}
        
        .section {{
            background: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 40px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.03);
        }}
        .section-title {{
            font-size: 1.8em;
            border-left: 6px solid #764ba2;
            padding-left: 15px;
            margin-bottom: 25px;
            color: #2d3436;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .section-stats {{
            font-size: 0.5em;
            background: #f1f3f5;
            padding: 5px 12px;
            border-radius: 20px;
            color: #495057;
            font-weight: normal;
        }}
        
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 10px;
        }}
        th {{
            background-color: #f8f9fa;
            color: #495057;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
            padding: 15px;
            border-bottom: 2px solid #dee2e6;
            text-align: left;
        }}
        td {{
            padding: 15px;
            border-bottom: 1px solid #f1f3f5;
            vertical-align: middle;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background-color: #fcfcfc; }}
        
        .count-badge {{
            display: inline-block;
            padding: 6px 14px;
            border-radius: 30px;
            font-weight: 700;
            font-size: 0.9em;
            min-width: 40px;
            text-align: center;
        }}
        .count-high {{ background-color: #d3f9d8; color: #2b8a3e; box-shadow: 0 2px 5px rgba(43,138,62,0.1); }}
        .count-medium {{ background-color: #fff3bf; color: #f08c00; box-shadow: 0 2px 5px rgba(240,140,0,0.1); }}
        .count-low {{ background-color: #ffe3e3; color: #e03131; box-shadow: 0 2px 5px rgba(224,49,49,0.1); }}
        .count-zero {{ background-color: #f1f3f5; color: #adb5bd; opacity: 0.6; }}
        
        .job-tag {{
            font-weight: 700;
            color: #4c6ef5;
            background: #edf2ff;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.95em;
        }}
        
        .base-text {{
            color: #495057;
            font-weight: 500;
        }}
        
        footer {{
            margin-top: 60px;
            padding: 40px;
            border-top: 1px solid #dee2e6;
            text-align: center;
            color: #adb5bd;
        }}
        
        @media (max-width: 768px) {{
            .summary {{ flex-direction: column; gap: 20px; }}
            .summary-item {{ border-right: none; border-bottom: 1px solid #eee; padding-bottom: 15px; }}
            .summary-item:last-child {{ border-bottom: none; }}
            th, td {{ padding: 10px; font-size: 0.85em; }}
            .section {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>동일상황 화이팅멘트 케이스 보고서</h1>
        <p>Q1(상황) × Q3(직렬) × Q4(베이스) 매칭 데이터 시각화</p>
    </header>

    <div class="summary">
        <div class="summary-item">
            <div class="summary-value">{total_categories}</div>
            <div class="summary-label">주요 상황 카테고리</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">{total_cases}</div>
            <div class="summary-label">전체 조합 케이스</div>
        </div>
        <div class="summary-item">
            <div class="summary-value">{total_reviews:,}</div>
            <div class="summary-label">매칭 완료 후기 수</div>
        </div>
    </div>
"""

    for section_name, items in data.items():
        section_total = sum(item['count'] for item in items)
        html_content += f"""
    <div class="section">
        <h2 class="section-title">
            {section_name}
            <span class="section-stats">총 {section_total}개 후기 매칭됨</span>
        </h2>
        <table>
            <thead>
                <tr>
                    <th style="width: 25%;">직렬 (Q3)</th>
                    <th style="width: 55%;">베이스 (Q4)</th>
                    <th style="width: 20%; text-align: center;">매칭 후기 수</th>
                </tr>
            </thead>
            <tbody>
"""
        for item in items:
            count = item['count']
            if count >= 20: badge_class = 'count-high'
            elif count >= 5: badge_class = 'count-medium'
            elif count > 0: badge_class = 'count-low'
            else: badge_class = 'count-zero'
            
            html_content += f"""
                <tr>
                    <td><span class="job-tag">{item['job']}</span></td>
                    <td class="base-text">{item['base']}</td>
                    <td style="text-align: center;">
                        <span class="count-badge {badge_class}">{count}</span>
                    </td>
                </tr>
"""
        html_content += """
            </tbody>
        </table>
    </div>
"""

    html_content += """
    <footer>
        <p>© 2026 동일상황 화이팅멘트 시스템 | 데이터 기반 자동 분석 보고서</p>
        <p style="font-size: 0.8em; margin-top: 5px;">본 보고서는 Markdown 소스 파일을 바탕으로 실시간 생성되었습니다.</p>
    </footer>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    # Use relative path or handle Windows backslashes properly
    input_file = os.path.join('답변정리', 'no02_동일상황화이팅멘트', 'no.02-동일상황화이팅멘트.md')
    output_file = 'case_report.html'
    
    data = parse_markdown(input_file)
    if data:
        generate_html(data, output_file)
        print(f"Report generated successfully: {output_file}")
    else:
        print("No data parsed. Check the input file path and format.")
