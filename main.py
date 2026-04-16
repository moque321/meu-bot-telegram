import os
import json
import random
import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ChatMemberHandler
from datetime import datetime, timedelta

# ===== CONFIG =====
GROUP_ID = -1001663495698
FORM_LINK = "https://docs.google.com/forms/d/e/1FAIpQLSfdopJ2f_Mm_o8LrYe5g2ry9MHmNek6LJ7plPbMQsPCBIgvEA/viewform?usp=publish-editor"
SECURITY_MSG = (
    "🔒 Segurança: Nenhum administrador irá entrar em contato com você por mensagem privada (DM).\n"
    "Toda comunicação oficial acontece apenas no grupo.\n"
    "Cuidado com golpes!"
)

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

try:
    creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
    print("Credenciais Google carregadas com sucesso.")
except KeyError:
    print("ERRO: variável GOOGLE_CREDENTIALS_JSON não encontrada.")
    raise
except json.JSONDecodeError as e:
    print("ERRO: falha ao decodificar GOOGLE_CREDENTIALS_JSON:", e)
    raise

recent_joins = {}
last_ranking_message_id = None

# ===== HELPERS =====
def get_sheet():
    """Sempre retorna uma conexão fresca com a planilha."""
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("bingx_tracking").sheet1

def safe_int(value):
    try:
        return int(value)
    except:
        return 0

def get_level(points):
    if points >= 50:
        return "💎 Diamante", None
    elif points >= 25:
        return "🥇 Ouro", 50 - points
    elif points >= 10:
        return "🥈 Prata", 25 - points
    elif points >= 5:
        return "🥉 Bronze", 10 - points
    else:
        return None, 5 - points

def get_sorted_records(limit=None):
    records = get_sheet().get_all_records()
    sorted_records = sorted(records, key=lambda x: safe_int(x["points"]), reverse=True)
    return sorted_records[:limit] if limit else sorted_records

async def delete_later(context, chat_id, message_id, delay=300):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or "sem_username"

    s = get_sheet()
    records = s.get_all_records()
    for row in records:
        if str(row["user_id"]) == user_id:
            sent = await update.message.reply_text(
                f"⚠️ Você já está participando!\n\n"
                f"⚠️ NÃO ESQUEÇA:\nPreencha o formulário para receber recompensas 👇\n{FORM_LINK}\n\n"
                f"{SECURITY_MSG}"
            )
            if update.effective_chat.type == "private":
                context.application.create_task(
                    delete_later(context, sent.chat_id, sent.message_id, 300)
                )
            return

    invite = await context.bot.create_chat_invite_link(chat_id=GROUP_ID)
    invite_link = invite.invite_link

    s.append_row([
        user_id,
        username,
        invite_link,
        0,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "FALSE"
    ])

    sent = await update.message.reply_text(
        f"🚀 Seu link exclusivo:\n\n{invite_link}\n\n"
        f"Convide amigos e suba no ranking 💸\n\n"
        f"⚠️ IMPORTANTE:\n"
        f"Para receber QUALQUER recompensa, você precisa preencher:\n"
        f"{FORM_LINK}\n\n"
        f"Sem isso, não conseguimos pagar 🚫\n\n"
        f"{SECURITY_MSG}"
    )
    if update.effective_chat.type == "private":
        context.application.create_task(
            delete_later(context, sent.chat_id, sent.message_id, 300)
        )

# ===== NOVO MEMBRO =====
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.chat_member.new_chat_member.status != "member":
        return

    new_user_id = str(update.chat_member.new_chat_member.user.id)

    now = datetime.now()
    if new_user_id in recent_joins:
        if now - recent_joins[new_user_id] < timedelta(seconds=30):
            return
    recent_joins[new_user_id] = now

    invite = update.chat_member.invite_link
    if invite is None:
        return

    invite_link = invite.invite_link
    s = get_sheet()
    records = s.get_all_records()

    for i, row in enumerate(records, start=2):
        if row["invite_link"] == invite_link:

            inviter_id = row["user_id"]
            username = row["username"]

            if inviter_id == new_user_id:
                return

            current_points = safe_int(row["points"])
            new_points = current_points + 1

            s.update_cell(i, 4, new_points)

            # DM ao convidador
            try:
                level, remaining = get_level(new_points)

                msg = f"🎉 +1 ponto!\n🔥 Total: {new_points}"

                if remaining:
                    msg += f"\n⏳ Faltam {remaining} para o próximo nível"

                msg += f"\n\n⚠️ Preencha o formulário:\n{FORM_LINK}"

                await context.bot.send_message(chat_id=inviter_id, text=msg)
            except:
                pass

            # Anúncio no grupo (mensagem aleatória)
            new_user = update.chat_member.new_chat_member.user
            new_username = new_user.username or new_user.first_name

            messages = [
                f"🚀 @{new_username} entrou pelo @{username}\n\n💰 +1 ponto\n👀 Quem tá ligado, tá na frente\n\n🏆 Total do @{username}: {new_points} pontos",
                f"💥 @{new_username} chegou pelo exército do @{username}\n\n+1 ponto na conta 📈\n\n🏆 Total do @{username}: {new_points} pontos",
                f"🎮 @{new_username} entrou no jogo pelo @{username}\n\n⚔️ +1 ponto conquistado\n\n🏆 Total do @{username}: {new_points} pontos",
                f"👑 @{username} trouxe mais um pro time\n\n👥 @{new_username} entrou agora\n💰 +1 ponto\n\n🏆 Total: {new_points} pontos",
                f"🔥 @{new_username} caiu na rede do @{username}\n\n💰 +1 ponto garantido\nQuem entendeu, tá farmando\n\n🏆 Total do @{username}: {new_points} pontos",
            ]

            await context.bot.send_message(
                chat_id=GROUP_ID,
                text=random.choice(messages)
            )

            # Level up
            old_level, _ = get_level(current_points)
            new_level, remaining = get_level(new_points)

            if new_level and new_level != old_level:
                await context.bot.send_message(
                    chat_id=GROUP_ID,
                    text=f"🏆 @{username} subiu para {new_level}!"
                )

            # Alerta de proximidade de nível
            if remaining and remaining <= 2:
                await context.bot.send_message(
                    chat_id=GROUP_ID,
                    text=f"👀 @{username} está a {remaining} convite(s) de subir de nível!"
                )

            break

# ===== RANKING (top 10) =====
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_ranking_message_id

    top = get_sorted_records(limit=10)

    if not top:
        await update.message.reply_text("📭 Nenhum usuário registrado ainda.")
        return

    msg = "🏆 Ranking da semana (Top 10):\n\n"
    for i, user in enumerate(top, start=1):
        msg += f"{i}. @{user['username']} — {user['points']} pontos\n"

    if update.effective_chat.type in ["group", "supergroup"]:
        if last_ranking_message_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=last_ranking_message_id
                )
            except:
                pass

        sent = await update.message.reply_text(msg)
        last_ranking_message_id = sent.message_id
    else:
        await update.message.reply_text(msg)

# ===== LINK =====
async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    records = get_sheet().get_all_records()

    for row in records:
        if str(row["user_id"]) == user_id:
            await update.message.reply_text(
                f"🔗 Seu link exclusivo de convite:\n\n{row['invite_link']}\n\n"
                f"Compartilhe e acumule pontos! 💸"
            )
            return

    await update.message.reply_text(
        "⚠️ Você ainda não está registrado. Use /start para se cadastrar."
    )

# ===== TOP 3 =====
async def top3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_sorted_records(limit=3)

    if not top:
        await update.message.reply_text("📭 Nenhum usuário registrado ainda.")
        return

    medals = ["🥇", "🥈", "🥉"]
    msg = "🏆 TOP 3 da semana:\n\n"

    for i, user in enumerate(top):
        msg += f"{medals[i]} @{user['username']} — {user['points']} pontos\n"

    await update.message.reply_text(msg)

# ===== MEU RANK =====
async def meurank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    sorted_records = get_sorted_records()

    for position, row in enumerate(sorted_records, start=1):
        if str(row["user_id"]) == user_id:
            points = safe_int(row["points"])
            await update.message.reply_text(
                f"📊 Você está em {position}º lugar com {points} ponto(s) esta semana!"
            )
            return

    await update.message.reply_text(
        "⚠️ Você ainda não está registrado. Use /start para se cadastrar."
    )

# ===== JOB: AVISO PRÉ-RESET (60s antes) =====
async def job_aviso_pre_reset(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text="🏆 Atenção! Em 60 segundos serão anunciados os TOP 3 vencedores da semana!"
    )

# ===== JOB: ANUNCIAR TOP 3 + RESET SEMANAL =====
async def job_reset_semanal(context: ContextTypes.DEFAULT_TYPE):
    top = get_sorted_records(limit=3)

    # Anuncia top 3 antes de resetar
    if top and any(safe_int(u["points"]) > 0 for u in top):
        medals = ["🥇", "🥈", "🥉"]
        msg = "🏆 TOP 3 da semana:\n"
        for i, user in enumerate(top):
            msg += f"{medals[i]} @{user['username']} — {user['points']} pontos\n"
        await context.bot.send_message(chat_id=GROUP_ID, text=msg)

    # Reseta pontos
    s = get_sheet()
    records = s.get_all_records()
    for i, row in enumerate(records, start=2):
        s.update_cell(i, 4, 0)

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text="🔄 Ranking resetado! Nova semana, novas chances 💸"
    )

# ===== MEUS PONTOS =====
async def meuspontos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    records = get_sheet().get_all_records()

    for row in records:
        if str(row["user_id"]) == user_id:
            points = safe_int(row["points"])
            await update.message.reply_text(
                f"📊 Seus pontos atuais:\n"
                f"💰 {points} ponto(s)\n\n"
                f"🚀 Continue convidando para subir no ranking!"
            )
            return

    await update.message.reply_text(
        "⚠️ Você ainda não está registrado. Use /start para participar."
    )

# ===== JOB: AVISO DE SEGURANÇA PERIÓDICO =====
async def job_aviso_seguranca(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=f"⚠️ {SECURITY_MSG}"
    )

# ===== JOB: TOP 5 A CADA 2 DIAS =====
async def job_top5_bidiario(context: ContextTypes.DEFAULT_TYPE):
    top = get_sorted_records(limit=5)

    if not top or all(safe_int(u["points"]) == 0 for u in top):
        return

    msg = "🔥 Top 5 atual:\n\n"
    for i, user in enumerate(top, start=1):
        msg += f"{i}. @{user['username']} — {user['points']} pontos\n"

    await context.bot.send_message(chat_id=GROUP_ID, text=msg)

# ===== DENUNCIAR =====
async def denunciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or "sem_username"

    admin_id = os.environ.get("ADMIN_USER_ID")
    if not admin_id:
        await update.message.reply_text(
            "⚠️ Não foi possível enviar sua denúncia no momento. Tente novamente mais tarde."
        )
        return

    descricao = " ".join(context.args) if context.args else None

    if not descricao:
        await update.message.reply_text(
            "ℹ️ Use o comando assim:\n/denunciar <descrição do que aconteceu>\n\n"
            "Exemplo:\n/denunciar Recebi uma mensagem privada de alguém dizendo ser admin e pedindo meus dados."
        )
        return

    relatorio = (
        f"🚨 Nova denúncia recebida!\n\n"
        f"👤 Usuário: @{username} (ID: {user_id})\n"
        f"📝 Descrição: {descricao}"
    )

    try:
        await context.bot.send_message(chat_id=admin_id, text=relatorio)
        await update.message.reply_text(
            "✅ Sua denúncia foi enviada ao administrador. Obrigado por ajudar a manter o grupo seguro!\n\n"
            f"{SECURITY_MSG}"
        )
    except Exception:
        await update.message.reply_text(
            "⚠️ Não foi possível enviar sua denúncia no momento. Tente novamente mais tarde."
        )

# ===== RESETLINK (ADMIN) =====
async def resetlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caller_id = str(update.effective_user.id)
    admin_id = os.environ.get("ADMIN_USER_ID", "")

    if caller_id != str(admin_id):
        await update.message.reply_text("🚫 Você não tem permissão para usar este comando.")
        return

    if not context.args:
        await update.message.reply_text(
            "ℹ️ Use o comando assim:\n/resetlink <user_id>\n\n"
            "Exemplo:\n/resetlink 123456789"
        )
        return

    target_id = context.args[0].strip()

    s = get_sheet()
    records = s.get_all_records()

    for i, row in enumerate(records, start=2):
        if str(row["user_id"]) == target_id:
            try:
                new_invite = await context.bot.create_chat_invite_link(chat_id=GROUP_ID)
                new_link = new_invite.invite_link

                s.update_cell(i, 3, new_link)

                await update.message.reply_text(
                    f"✅ Link do usuário {target_id} (@{row['username']}) atualizado!\n\n"
                    f"🔗 Novo link:\n{new_link}"
                )
            except Exception as e:
                await update.message.reply_text(
                    f"⚠️ Erro ao gerar novo link: {e}"
                )
            return

    await update.message.reply_text(
        f"⚠️ Nenhum usuário encontrado com o ID {target_id}."
    )

# ===== BOT =====
try:
    _token = os.environ["TELEGRAM_TOKEN"]
except KeyError:
    print("ERRO: variável TELEGRAM_TOKEN não encontrada.")
    raise

app = ApplicationBuilder().token(_token).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ranking", ranking))
app.add_handler(CommandHandler("link", link))
app.add_handler(CommandHandler("top3", top3))
app.add_handler(CommandHandler("meurank", meurank))
app.add_handler(CommandHandler("meuspontos", meuspontos))
app.add_handler(CommandHandler("denunciar", denunciar))
app.add_handler(CommandHandler("resetlink", resetlink))
app.add_handler(ChatMemberHandler(new_member, ChatMemberHandler.CHAT_MEMBER))

# Aviso 60s antes do reset semanal
app.job_queue.run_repeating(job_aviso_pre_reset, interval=604800, first=604740)
# Anúncio top 3 + reset semanal
app.job_queue.run_repeating(job_reset_semanal, interval=604800, first=604800)
# Top 5 a cada 2 dias
app.job_queue.run_repeating(job_top5_bidiario, interval=172800, first=172800)
# Aviso de segurança a cada 12 horas
app.job_queue.run_repeating(job_aviso_seguranca, interval=43200, first=43200)

# ===== MAIN LOOP =====
async def main():
    print("BOT INICIANDO...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=["message", "chat_member"],
        drop_pending_updates=True
    )
    print("BOT RODANDO EM PRODUÇÃO")
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
