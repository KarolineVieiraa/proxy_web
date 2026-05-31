from flask import Flask, request, Response, render_template
import requests, json, re, os
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from urllib.parse import urljoin

#Configura o diretório de templates para o Flask
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
#Iniciando o Flask
app = Flask(__name__, template_folder=template_dir)

#Sessão global para reutilizar conexões HTTP e melhorar o desempenho
session = requests.Session()

#ADICIONANDO VARIÁVEIS DE CACHE
#Para evitar a leitura repetida de disco em cada requisição
_cached_blocked_sites = []
_cached_words = {}

#Função para atualizar o cache dos sites bloqueados e das palavras
def refresh_cache():
    #Carrega os sites bloqueados e as palavras para o cache global
    global _cached_blocked_sites, _cached_words
    try:
        #Tenta carregar os sites bloqueados do arquivo 'blocked.json'
        with open('blocked.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            #Armazena eles na variável global _cached_blocked_sites.
            _cached_blocked_sites = data.get('bloqueados', [])
    except:
        #Se o arquivo não existir ou ocorrer um erro, ele define _cached_blocked_sites como uma lista vazia.
        _cached_blocked_sites = []

    #Tenta carregar as palavras do arquivo 'words.json'
    try:
        with open('words.json', 'r', encoding='utf-8') as f:
            #Armazena o dicionário de palavras na variável global
            _cached_words = json.load(f)
    #Se o arquivo não existir ou ocorrer um erro, ele define _cached_words como um dicionário vazio.
    except:
        _cached_words = {}

# Chamamos a função uma vez ao iniciar
refresh_cache()

# Agora, as funções de load apenas retornam o cache
def load_blocked_sites():
    return _cached_blocked_sites

def load_words():
    return _cached_words

'''PARTE DO CÓDIGO DESATIVADA, POIS A LÓGICA FOI REESCRITA PARA USAR CACHE E EVITAR LEITURA DE DISCO EM CADA REQUISIÇÃO
#função para carregar os sites bloqueados em JSON
def load_blocked_sites():
    #Essa função tenta abrir o arquivo 'blocked.json' e carregar a lista de sites bloqueados.
    try:
        with open('blocked.json', 'r', encoding='utf-8') as f:
            data = json.load(f) #Carrega o conteúdo do arquivo JSON em um dicionário Python
            return data.get('bloqueados', [])#Acessa a chave 'bloqueados' do dicionário e retorna a lista associada a essa chave.
    except FileNotFoundError:#Se o arquivo 'blocked.json' não for encontrado, a função captura a exceção FileNotFoundError
        return []#Se o arquivo não existir, ela retorna uma lista vazia.

#Essa função carrega o dicionário de palavras que serão substituídas
def load_words():
    #Essa função tenta abrir o arquivo 'words.json' e carregar o dicionário de palavras.
    try:
        with open('words.json', 'r', encoding='utf-8') as f:
            return json.load(f)#Carrega o conteúdo do arquivo JSON em um dicionário Python e o retorna.
    except FileNotFoundError:#Se o arquivo 'words.json' não for encontrado, a função captura a exceção FileNotFoundError
        return {} #Se o arquivo não existir, ela retorna um dicionário vazio.
'''

#Essa função escreve no ficheiro log.json cada tentativa de acesso
def log_access(url, action):
    #Essa função registra o acesso a um URL específico, juntamente com a ação realizada 
    #(permitido, bloqueado, filtrado ou erro).
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), #Registra o momento
        'url': url,
        'action': action #Se foi permitido, bloqueado, filtrado ou se ocorreu um erro
    }

    #Essa parte do código tenta abrir o arquivo 'log.json' para ler os logs existentes.
    try:    
        with open('log.json', 'r', encoding='utf-8') as f:
            logs = json.load(f)#Se o arquivo não existir ou estiver vazio,
    except (FileNotFoundError, json.JSONDecodeError):#ele captura as exceções FileNotFoundError e JSONDecodeError, respectivamente, 
        logs = [] #e inicializa a variável logs como uma lista vazia.

    #Adiciona o novo acesso à lista
    logs.append(log_entry)

    #Abre o arquivo 'log.json' para escrita
    with open('log.json', 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False) #Guarda o log formatado

#Essa função aplica a substituição de palavras no conteúdo HTML 
def filter_content(html, words_dict):#Recebe o conteúdo HTML e o dicionário de palavras a serem substituídas
    for bad_word, replacement in words_dict.items():#Itera sobre cada par de palavra proibida e sua substituição no dicionário
        html = re.sub(re.escape(bad_word), replacement, html, flags=re.IGNORECASE)#Substitui todas as ocorrências da palavra proibida no conteúdo HTML pela palavra de substituição, ignorando diferenças de maiúsculas e minúsculas.
    return html#Retorna o conteúdo HTML modificado, com as palavras proibidas substituídas pelas palavras de substituição definidas no dicionário.

#Essa função ajusta os URLs(href/src) para que o utilizador continue dentro do proxy
def rewrite_urls(html, base_url): #Recebe o conteúdo HTML e a URL base do site original para reescrever os links corretamente
    soup = BeautifulSoup(html, 'html.parser')

    #Lista de atributos HTML que contêm URLs
    tags_attrs = {
        'a': 'href',
        'link': 'href',
        'script': 'src',
        'img': 'src',
        'form': 'action' 
    }

    for tag, attr in tags_attrs.items():
        for element in soup.find_all(tag, **{attr: True}):
            original_url = element[attr]
            
            #Não reescreve URLs que já passam pelo proxy (evita loops infinitos)
            if original_url.startswith('http') and '127.0.0.1:5000' in original_url:
                continue
            #Ignora domínios externos comuns de recursos (como fontes e vídeos) para evitar quebrar o layout e funcionalidades dos sites
            external_domains = ['fonts.googleapis.com', 'fonts.gstatic.com', 'use.fontawesome.com', 'youtube.com']
            #Verifica se a URL original contém algum dos domínios externos listados e, se sim, ela pula a reescrita dessa URL para evitar quebrar o layout e funcionalidades dos sites. Isso é importante para garantir que recursos como fontes e vídeos continuem funcionando corretamente, mesmo que o proxy não possa reescrever esses links de forma segura.
            if any(domain in original_url for domain in external_domains):
                continue

            # Se o link não for absoluto (já começa com http), ele converte para absoluto
            full_url = urljoin(base_url, original_url)
            
            # Remove o protocolo da URL original para que o proxy trate como um caminho relativo
            clean_url = full_url.replace("https://", "").replace("http://", "")

            # Força o link a passar pelo seu proxy (localhost:5000)
            element[attr] = f"http://127.0.0.1:5000/{clean_url}"
            
    return str(soup)

#Essa função gera a página de bloqueio personalizada
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
            <h1>Patrulha das meninas bloqueou esse site</h1>
            <p>O site <span class="domain">{domain}</span> foi bloqueado.</p>
            <p>Em caso de duvidas, fale com o Tribunal de Minúsculas Causas.</p>
        </div>
    </body>
    </html>
    """

#Rotas principais do flask
#Rota que captura todos os endereços solicitados
#ADIÇÃO DAS ROTAS POST PARA LOGIN DE DADOS
@app.route('/', defaults={'path': ''},methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    #Define a URL e adicioa automaticamente no protocolo
    full_url = path if path else request.args.get('url', '')

    #Verifica se a URL está vazia ou é apenas uma barra
    if not full_url or full_url == '':
        #retorna uma página inicial simples com instruções para o usuário
        return render_template('index.html'), 200 #Retorna status "OK" para a página inicial
    
    #Formatação da URL caso o usuário não escreva o HTTP
    if full_url and not full_url.startswith('http'):
        #Tenta o https primeiro, para sites que redirecionam automaticamente para HTTPS
        full_url = 'https://' + full_url

    '''return """
        <div style="text-align: center; font-family: sans-serif; padding-top: 50px;">
            <h1>🌸 Web Proxy das meninas 🌸</h1>
            <p>Este é um espaço privado e curado. Para acessar, digite o URL logo após a barra:</p>
            <p style="background': #f0f0f0; padding: 10px;">http://localhost:5000/http://www.exemplo.com</p>
        </div> """, 200 #Retorna status "OK" para a página inicial'''
    
    #Verifica se a URL termina com um '?' e remove, para evitar problemas de parsing
    if full_url.endswith('?'):
        full_url = full_url[:-1]

    #Para que o proxy ignore as requisições automáticas do navegador pelo ícone (evita poluir o log)
    if request.path == '/favicon.ico':
        return '', 204 #Retorna status "No Content" para o navegador parar de tentar

    #Analisa a URL para extrair o domínio, que será usado para verificar se o site está bloqueado
    parsed = urlparse(full_url)
    domain = parsed.netloc

    # Remove 'www.' para que furg.br e www.furg.br sejam tratados iguais
    domain_clean = domain.replace('www.', '')

    #Carrega a lista de sites bloqueados e o dicionário de palavras proibidas
    blocked_sites = load_blocked_sites()
    words_dict = load_words()

    #Verifica se o domínio da URL solicitada está na lista de sites bloqueados.
    if domain_clean in blocked_sites:
        log_access(full_url, 'bloqueado') #Se estiver, registra o acesso como "bloqueado" no log
        return render_template('bloqueado.html', domain=domain_clean), 403#e retorna a página de bloqueio personalizada com status 403 (Forbidden).

    #Ele tenta buscar o conteúdo do site real
    try:

        #PEGANDO OS MÉTODOS POST E GET
        if request.method == 'POST':
            # Requisição POST e repassando os dados do formulário
            response = requests.post(full_url, data=request.form, timeout=10, allow_redirects=True)
        else:
            # Session GET e repassando os parâmetros da URL
            # é usado o session e não request para que o proxy possa lidar melhor 
            # com cookies e conexões persistentes e melhorar o desempenho geral.
            response = session.get(full_url, timeout=10, allow_redirects=True)
        
        #Define a codificação da resposta como UTF-8 para garantir que os caracteres sejam interpretados corretamente.
        response.encoding = 'utf-8'

        # Verifica se é uma requisição de recurso (CSS, JS, Imagem)
        is_resource = any(ext in full_url.lower() for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.json', '.svg'])
       
        #Verifica se a resposta é um redirecionamento para HTTPS, mesmo que a requisição original seja HTTP. Isso é importante para evitar que o proxy saia do ar ao clicar em um link que redireciona para HTTPS.
        if response.headers.get('Location', '').startswith('https') and not is_resource:
            return render_template('erro_https.html'), 403
        
        #Preparação dos headers para a resposta, removendo os que podem causar problemas de compatibilidade
        headers = {k: v for k, v in response.headers.items() if k.lower() not in ['content-encoding', 'content-length', 'transfer-encoding']}
        
        #Verifica o tipo de conteúdo da resposta para decidir se deve aplicar o filtro de palavras ou apenas reescrever os URLs. Ele verifica se o tipo de conteúdo é 'text/html' e se o dicionário de palavras não está vazio antes de aplicar o filtro.
        content_type = response.headers.get('Content-Type', '')
        
        #FLUXO ANTIGO DE REQUISIÇÃO, ANTES DE ADICIONAR O SUPORTE A POST
        '''#Requisição GET para o site original usando a URL completa, com um timeout de 10 segundos e permitindo redirecionamentos.
        response = requests.get(full_url, timeout=10, allow_redirects=True)
        response.encoding = 'utf-8' #Define a codificação da resposta como UTF-8 para garantir que os caracteres sejam interpretados corretamente.
        #Verifica se o site é HTTP ou HTTPS
        if response.status_code in [301, 302]:
            return "<h1>Site usa HTTPS</h1><p>Nosso proxy didático não consegue processar sites seguros (HTTPS).</p>", 403
        #Cria um dicionário de headers a partir dos headers da resposta original para garantir que as informações de cabeçalho sejam preservadas na resposta do proxy.
        headers = dict(response.headers)
        #Remove headers que causam problemas de compatibilidade na retransmissão
        headers.pop('Content-Encoding', None)
        headers.pop('Content-Length', None)
        headers.pop('Transfer-Encoding', None)'''

        #PARTE DO CÓDIGO ATUALIZADA PARA QUE O PROXY NÃO SAIA DO AR AO CLICAR EM ALGUM LINK
        #Verifica se o tipo de conteúdo é 'text/html' e se o HTML contém palavras a filtrar
        '''if 'text/html' in content_type and words_dict:
            #Se sim, ele armazena o conteúdo HTML original em uma variável e aplica o filtro de palavras usando a função filter_content.
            #O resultado do filtro é armazenado em filtered_content.
            original_html = response.text
            filtered_content = original_html

            #Agora só aplicará o filtro se o words_dict não estiver vazio
            if words_dict:
                filtered_content = filter_content(original_html, words_dict)
            
            # Reescreve as URLs mesmo que o filtro não tenha alterado o conteúdo,
            # para garantir que os links continuem funcionando
            final_content = rewrite_urls(filtered_content, full_url)

            #Verifica se o texto mudou para definie o log correto
            if original_html != filtered_content:
                log_access(full_url, 'filtrado')
            else:#Se não, ele registra o acesso como "permitido" no log.
                log_access(full_url, 'permitido')

            #Retorna a resposta com o conteúdo final (filtrado e com URLs reescritas), status da resposta original, headers ajustados e tipo MIME 'text/html'.
            return Response(final_content.encode('utf-8'), status=response.status_code, headers=headers, mimetype='text/html')
        '''

        #Verifica se o tipo de conteúdo é 'text/html'
        if 'text/html' in content_type:
                content = response.text
                words_dict = load_words()
                
                # Aplica filtro se houver palavras
                if words_dict:
                    filtered_content = filter_content(content, words_dict)
                    if content != filtered_content:
                        log_access(full_url, 'filtrado')
                        content = filtered_content
                    else:
                        log_access(full_url, 'permitido')
                else:
                    log_access(full_url, 'permitido')

                final_content = rewrite_urls(content, full_url)
                #Criamos a resposta antes do return
                response_data = Response(final_content.encode('utf-8'), status=response.status_code, headers=headers, mimetype='text/html; charset=utf-8')
                
                # Adicionamos o CORS para permitir que os recursos (CSS/JS) carreguem
                response_data.headers['Access-Control-Allow-Origin'] = '*'
                
                return response_data
        
        #Verificação para sites que tentam redirecionar para HTTPS, mesmo que a requisição original seja HTTP.
        #Isso é importante para evitar que o proxy saia do ar ao clicar em um link que redireciona para HTTPS.
        #Isso acontece apenas em sites que exigem a segurança HTTPS, como logins
        '''if 'https' in full_url or response.headers.get('Location', '').startswith('https'):
            return """
            <div style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>🌸 Ops! Proteção de Navegação 🌸</h1>
                <p>O site que você acessou tentou migrar para uma conexão segura (HTTPS).</p>
                <p>Nosso proxy didático foca em monitoramento HTTP. Para sua segurança, interrompemos a conexão.</p>
                <a href="/">Voltar para a Patrulha</a>
            </div>
            """, 403'''

        #Outros conteúdos (imagens, CSS)
        log_access(full_url, 'permitido')
        #Criamos a resposta antes do return
        res = Response(response.content, status=response.status_code, headers=headers)
        res.headers['Access-Control-Allow-Origin'] = '*' #Adiciona o CORS para permitir que os recursos (CSS/JS) carreguem
        return res

        #ESSA PARTE DO CÓDIGO FOI DESATIVADA, POIS A LÓGICA FOI REESCRITA PARA APLICAR O FILTRO APENAS 
        #SE O words_dict NÃO ESTIVER VAZIO, E PARA REESCREVER AS URLs INDEPENDENTEMENTE 
        #DE O FILTRO TER SIDO APLICADO OU NÃO.
        '''filtered_content = filter_content(response.text, words_dict)
            filtered_content = rewrite_urls(filtered_content, full_url)
            log_access(full_url, 'filtrado')
            return Response(filtered_content, status=response.status_code,
                          headers=headers, mimetype='text/html')'''

        #lÓGICA DESATIVADA AFIM DE MELHORAR O FLUXO GET E POST
        '''#Caso seja html mas não haja palavras a filtrar, ele reescreve as URLs para garantir que os links continuem funcionando, registra o acesso como "permitido" no log e retorna o conteúdo original sem aplicar o filtro.
        elif 'text/html' in content_type:
            content = rewrite_urls(response.text, full_url)
            log_access(full_url, 'permitido')
            #Retorna o conteúdo original sem aplicar o filtro, registrando o acesso como "permitido" no log.
            return Response(content, status=response.status_code, headers=headers, mimetype='text/html')
        #Caso o conteúdo não seja HTML, ele retorna a resposta original sem modificações, registrando o acesso como "permitido" no log.
        else:
            log_access(full_url, 'permitido')
            #Retorna a resposta original sem modificações, registrando o acesso como "permitido" no log.
            return Response(response.content, status=response.status_code, headers=headers)'''
    
    #Se ocorrer um erro durante a requisição ao site original, como um timeout ou um erro de conexão, ele captura a exceção RequestException
    except requests.exceptions.RequestException as e:
        #Registra o acesso como "erro" no log
        log_access(full_url, f'erro: {str(e)}')
        #Retorna uma página de erro personalizada com o status 500 (Internal Server Error).
        return f"""
        <div style="text-align: center; font-family: sans-serif; color: #555;">
            <h1>Ops!</h1>
            <p>O site solicitado está passando por um momento de indisponibilidade técnica.</p>
            <p><i>Erro: {str(e)}</i></p>
        </div>
        """, 500

#Rota para atualizar o cache manualmente, caso os arquivos sejam editados enquanto o servidor está rodando
@app.route('/refresh')
def manual_refresh():
    refresh_cache()
    return "Cache atualizado com sucesso!", 200

#Inicia o servidor Flask na porta 5000, permitindo conexões de qualquer endereço IP (host='
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
