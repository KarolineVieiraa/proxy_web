# Web Proxy com Flask

Proxy web simples que implementa bloqueio de sites e filtro de conteudo.

## Escolha de Tecnologia

**Python:** Alem da linguagem ser simples era a stack mais conhecida da nossa dupla, legibilidade boa para um projeto rápido.

**Flask:** Framework simples e conhecido e nossa dupla ja tinha trabalhado anteriormente.

## Instalacao

### Passo 1: Criar ambiente virtual (DICA DE AMIGAS HAHAH evita que sua maquina fique com 1 milhão de conflito de versoes)

Antes de instalar qualquer biblioteca, crie um ambiente virtual. Isso mantem as dependencias deste projeto isoladas do resto do seu sistema.
Obs: muda dependendo do seu sistema operacional
```bash
python3 -m venv nome_do_ambiente
```

Por exemplo:
```bash
python3 -m venv venv
```

### Passo 2: Ativar o ambiente virtual

No macOS/Linux:
```bash
source venv/bin/activate
```

No Windows:
```bash
venv\Scripts\activate
```

### Passo 3: Instalar as dependencias

Com o ambiente virtual ativado, instale as bibliotecas necessarias:

```bash
pip install -r requirements.txt
```

## Como usar

1. Inicie o servidor:
```bash
python app.py
```

3. Acesse sites atraves do proxy usando o formato:
```
http://localhost:5000/http://www.exemplo.com
```

## Funcionalidades

### 1. Modo Transparente
Sites nao bloqueados sao acessados normalmente, com o proxy repassando o conteudo.

### 2. Bloqueio de Sites
Sites listados em `blocked.json` sao bloqueados e retornam uma pagina de aviso.

### 3. Filtro de Conteudo
Palavras listadas em `words.json` sao substituidas automaticamente.

### 4. Log de Acessos
Todas as requisicoes sao registradas em `log.json` com timestamp, URL e acao executada.

## Exemplos de Uso

```
# Acesso normal
http://localhost:5000/http://www.google.com

# Site bloqueado (configurado em blocked.json)
http://localhost:5000/http://www.sitex.com

# Conteudo filtrado (se contiver palavras do words.json)
http://localhost:5000/http://qualquersite.com
```

## Estrutura dos Arquivos de Configuracao

### blocked.json
```json
{
  "bloqueados": [
    "www.sitex.com",
    "redes-sociais.net",
    "joguinhos.io"
  ]
}
```

### words.json
```json
{
  "foda": "diabos",
  "merda": "macacos me mordam",
  "idiota": "ingenuo"
}
```


