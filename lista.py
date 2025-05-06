from telegram import Bot
from telegram.error import TelegramError
import datetime
import html
import logging
import asyncio
import json
import re

# Configurar logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_html_report(chats):
    """Gera um relatório HTML dos grupos ordenados por quantidade de membros (decrescente)"""
    # Ordenar grupos por número de membros (decrescente)
    sorted_chats = sorted(chats, key=lambda x: x['members_count'], reverse=True)
    
    html_content = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Relatório de Grupos do Telegram</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }
            h1 {
                color: #0088cc;
                text-align: center;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            th, td {
                padding: 12px 15px;
                border: 1px solid #ddd;
                text-align: left;
            }
            th {
                background-color: #0088cc;
                color: white;
                position: sticky;
                top: 0;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            tr:hover {
                background-color: #e1f5fe;
            }
            .timestamp {
                font-size: 0.8em;
                text-align: center;
                margin-top: 20px;
                color: #666;
            }
            a {
                color: #0088cc;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <h1>Relatório de Grupos do Telegram</h1>
        <table>
            <thead>
                <tr>
                    <th>Nome do Grupo</th>
                    <th>Quantidade de Membros</th>
                    <th>Data de Criação</th>
                    <th>Link de Convite</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for chat in sorted_chats:
        # Garantir que o link de convite existe
        invite_link = chat['invite_link'] if chat['invite_link'] else "#"
        
        html_content += f"""
                <tr>
                    <td>{html.escape(chat['title'])}</td>
                    <td>{chat['members_count']}</td>
                    <td>{chat['created_date']}</td>
                    <td><a href="{invite_link}" target="_blank">Link de Convite</a></td>
                </tr>
        """
    
    current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    html_content += f"""
            </tbody>
        </table>
        <div class="timestamp">Relatório gerado em: {current_time}</div>
    </body>
    </html>
    """
    
    # Salvar o arquivo HTML
    with open("relatorio_grupos_telegram.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    logger.info(f"Relatório HTML gerado com sucesso: relatorio_grupos_telegram.html")
    return len(sorted_chats)

def get_chat_creation_date(chat):
    """
    Obter uma estimativa de data de criação com base no ID do chat.
    Os IDs do Telegram contêm timestamps, mas isso é uma aproximação.
    """
    # O ID do chat no Telegram às vezes contém informações sobre quando foi criado
    # Esta é uma estimativa aproximada
    if hasattr(chat, 'id') and chat.id:
        # Usando os primeiros dígitos como timestamp aproximado
        # Isso não é oficial, mas pode dar uma ideia aproximada para alguns chats
        chat_id_str = str(abs(chat.id))
        if len(chat_id_str) > 5:
            timestamp_part = int(chat_id_str[:10])
            try:
                date = datetime.datetime.fromtimestamp(timestamp_part)
                return date.strftime("%d/%m/%Y")
            except:
                pass
    return "Desconhecida"

def read_chat_ids_from_file(filename):
    """Lê os IDs dos chats de um arquivo JSON ou de texto"""
    chat_ids = []
    try:
        with open(filename, 'r') as file:
            content = file.read().strip()
            
            # Tentar interpretar como JSON
            try:
                # Corrigir JSON potencialmente malformado
                # Adicionar colchete de fechamento se estiver faltando
                if content.startswith('[') and not content.strip().endswith(']'):
                    content += ']'
                
                # Remover vírgulas extras no final
                content = re.sub(r',\s*]', ']', content)
                
                # Tentar parser como JSON
                chat_ids = json.loads(content)
                
                # Verificar se é uma lista
                if not isinstance(chat_ids, list):
                    logger.warning("O arquivo não contém uma lista de IDs. Tentando outro método...")
                    chat_ids = []
            except json.JSONDecodeError:
                logger.warning("Não foi possível interpretar o arquivo como JSON. Tentando outro método...")
                
            # Se o JSON falhou, tentar interpretar como lista simples de números
            if not chat_ids:
                # Extrair números com regex
                matches = re.findall(r'-?\d+', content)
                chat_ids = [int(match) for match in matches]
        
        # Filtrar apenas IDs válidos (remover zeros ou valores não numéricos)
        chat_ids = [chat_id for chat_id in chat_ids if isinstance(chat_id, int) and chat_id != 0]
        
        logger.info(f"Encontrados {len(chat_ids)} IDs de chat no arquivo.")
        return chat_ids
    except Exception as e:
        logger.error(f"Erro ao ler o arquivo de IDs: {e}")
        return []

async def process_chats(bot, chat_ids):
    """Processa cada chat para obter informações detalhadas"""
    chat_info_list = []
    
    total = len(chat_ids)
    for i, chat_id in enumerate(chat_ids, 1):
        try:
            print(f"Processando chat {i}/{total}: {chat_id}")
            
            # Obter informações detalhadas do chat
            detailed_chat = await bot.get_chat(chat_id=chat_id)
            
            # Tentar obter o número de membros
            try:
                members_count = await bot.get_chat_member_count(chat_id=chat_id)
            except Exception as e:
                logger.warning(f"Não foi possível obter contagem de membros para '{detailed_chat.title}': {e}")
                members_count = 0
            
            # Tentar obter o link de convite
            invite_link = None
            try:
                # Verificar se já existe um link de convite
                if hasattr(detailed_chat, 'invite_link') and detailed_chat.invite_link:
                    invite_link = detailed_chat.invite_link
                else:
                    # Tentar criar um novo link de convite (requer permissões de admin)
                    invite_link = await bot.export_chat_invite_link(chat_id=chat_id)
            except Exception as e:
                logger.warning(f"Não foi possível obter/criar link de convite para '{detailed_chat.title}': {e}")
                # Se não conseguimos criar um link, vamos tentar usar um link padrão para grupos públicos
                if hasattr(detailed_chat, 'username') and detailed_chat.username:
                    invite_link = f"https://t.me/{detailed_chat.username}"
            
            # Obter data de criação aproximada
            created_date = get_chat_creation_date(detailed_chat)
            
            # Adicionar informações do chat à lista
            chat_info = {
                'title': detailed_chat.title or "Chat sem título",
                'members_count': members_count,
                'created_date': created_date,
                'invite_link': invite_link
            }
            
            chat_info_list.append(chat_info)
            logger.info(f"Processado: {detailed_chat.title} ({members_count} membros)")
            
        except Exception as e:
            logger.error(f"Erro ao processar chat {chat_id}: {e}")
    
    return chat_info_list

async def main():
    # Solicitar o token do bot
    bot_token = input("Digite o token do seu bot: ")
    
    # Solicitar o nome do arquivo com os IDs dos chats
    filename = input("Digite o nome do arquivo com os IDs dos chats (padrão: chat_ids.json): ") or "chat_ids.json"
    
    try:
        logger.info("Conectando ao Telegram...")
        bot = Bot(token=bot_token)
        
        # Verificar conexão obtendo informações do bot
        bot_info = await bot.get_me()
        logger.info(f"Conectado como: {bot_info.first_name} (@{bot_info.username})")
        
        # Ler os IDs dos chats do arquivo
        logger.info(f"Lendo IDs dos chats do arquivo: {filename}")
        chat_ids = read_chat_ids_from_file(filename)
        
        if not chat_ids:
            logger.error("Nenhum ID de chat válido encontrado no arquivo.")
            print(f"\nNenhum ID de chat válido encontrado no arquivo '{filename}'.")
            print("Verifique se o arquivo contém uma lista de IDs no formato JSON, por exemplo:")
            print("[-1001234567890, -1009876543210]")
            return
        
        # Processar os chats para obter informações detalhadas
        logger.info(f"Processando {len(chat_ids)} chats...")
        chat_info_list = await process_chats(bot, chat_ids)
        
        # Gerar relatório HTML
        if chat_info_list:
            total_chats = generate_html_report(chat_info_list)
            logger.info(f"Relatório gerado com {total_chats} grupos.")
            print(f"\nRelatório HTML gerado com sucesso contendo {total_chats} grupos.")
            print("Arquivo: relatorio_grupos_telegram.html")
        else:
            logger.warning("Nenhum chat encontrado para gerar relatório.")
            print("\nNenhum chat processado com sucesso. Verifique se:")
            print("1. Os IDs dos chats estão corretos")
            print("2. O bot é membro dos grupos especificados")
            print("3. O bot tem permissões necessárias")
    
    except TelegramError as te:
        logger.error(f"Erro do Telegram: {te}")
        print(f"\nErro do Telegram: {te}")
        if "Unauthorized" in str(te):
            print("Token inválido. Verifique o token do bot e tente novamente.")
    except Exception as e:
        logger.error(f"Erro ao executar o script: {e}")
        print(f"\nOcorreu um erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())
