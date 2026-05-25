from flask import Flask, request, Response
import requests
import json
import re
from datetime import datetime
from urllib.parse import urlparse, urljoin

app = Flask(__name__)

def load_blocked_sites():
    try:
        with open('blocked.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('bloqueados', [])
    except FileNotFoundError:
        return []

def load_words():
    try:
        with open('words.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def log_access(url, action):
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'url': url,
        'action': action
    }

    try:
        with open('log.json', 'r', encoding='utf-8') as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []

    logs.append(log_entry)

    with open('log.json', 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

def filter_content(html, words_dict):
    for bad_word, replacement in words_dict.items():
        html = re.sub(re.escape(bad_word), replacement, html, flags=re.IGNORECASE)
    return html

def rewrite_urls(html, base_url):
    parsed_base = urlparse(base_url)
    scheme = parsed_base.scheme
    netloc = parsed_base.netloc

    html = re.sub(r'(href|src)=["\']https?://([^"\']+)["\']',
                  r'\1="http://127.0.0.1:5000/\2"', html)

    html = re.sub(r'(href|src)=["\'](//[^"\']+)["\']',
                  fr'\1="http://127.0.0.1:5000/{scheme}:\2"', html)

    html = re.sub(r'(href|src)=["\'](/[^/][^"\']*)["\']',
                  fr'\1="http://127.0.0.1:5000/{scheme}://{netloc}\2"', html)

    return html

def blocked_page(domain):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Acesso Bloqueado</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #FFB6C1 0%, #FFC0CB 100%);
                color: #fff;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                background-color: rgba(255, 255, 255, 0.2);
                padding: 50px;
                border-radius: 20px;
                box-shadow: 0 8px 32px rgba(255, 105, 180, 0.3);
                backdrop-filter: blur(10px);
            }}
            .icon {{
                font-size: 5em;
                margin-bottom: 20px;
            }}
            h1 {{
                font-size: 2.5em;
                margin: 20px 0;
                color: #FF1493;
                text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
            }}
            p {{
                font-size: 1.3em;
                color: #fff;
                text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1);
            }}
            .domain {{
                color: #FF69B4;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">🌸</div>
            <h1>Patrulha da Larinha bloqueou esse site</h1>
            <p>O site <span class="domain">{domain}</span> foi bloqueado.</p>
            <p>Em caso de duvidas, fale com o Tribunal de Minusculas Causas.</p>
        </div>
    </body>
    </html>
    """

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def proxy(path):
    full_url = request.full_path.lstrip('/?')

    if not full_url or full_url == '':
        return """
        <h1>Web Proxy</h1>
        <p>Use o formato: http://localhost:5000/http://www.exemplo.com</p>
        """, 200

    if full_url.endswith('?'):
        full_url = full_url[:-1]

    parsed = urlparse(full_url)
    domain = parsed.netloc

    blocked_sites = load_blocked_sites()
    words_dict = load_words()

    if domain in blocked_sites:
        log_access(full_url, 'bloqueado')
        return blocked_page(domain), 403

    try:
        response = requests.get(full_url, timeout=10, allow_redirects=True)

        headers = dict(response.headers)
        headers.pop('Content-Encoding', None)
        headers.pop('Content-Length', None)
        headers.pop('Transfer-Encoding', None)

        content_type = response.headers.get('Content-Type', '')

        if 'text/html' in content_type and words_dict:
            filtered_content = filter_content(response.text, words_dict)
            filtered_content = rewrite_urls(filtered_content, full_url)
            log_access(full_url, 'filtrado')
            return Response(filtered_content, status=response.status_code,
                          headers=headers, mimetype='text/html')
        elif 'text/html' in content_type:
            content = rewrite_urls(response.text, full_url)
            log_access(full_url, 'permitido')
            return Response(content, status=response.status_code,
                          headers=headers, mimetype='text/html')
        else:
            log_access(full_url, 'permitido')
            return Response(response.content, status=response.status_code,
                          headers=headers)

    except requests.exceptions.RequestException as e:
        log_access(full_url, f'erro: {str(e)}')
        return f"<h1>Erro ao acessar o site</h1><p>{str(e)}</p>", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
