import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import os
import requests
from telegram import Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from datetime import datetime
import re

API_TOKEN = "7823114637:AAFygTDDBhPEKuut6Hhv-qhFe13AQDNT0L0"
VIDEO_FOLDER = "trailers"
ADMIN_ID =  5116530698 # Remplacez par votre ID Telegram

# Statistiques globales
stats = {
    "recherches_total": 0,
    "anime_trouves": 0,
    "utilisateurs_uniques": set(),
    "derniere_recherche": None
}

# Liste des administrateurs
admins = {ADMIN_ID}  # Ajoutez l'ID de l'admin principal ici

# Liste des utilisateurs bannis
banned_users = set()

# Base de données locale (pour la commande /add_anime)
anime_database = {}

# ✅ Fonction de vérification admin
def is_admin(user_id):
    return user_id in admins

# 🚫 Fonction de vérification banni
def is_banned(user_id):
    return user_id in banned_users

# 🔍 Fonction de traduction automatique améliorée
def translate_to_french(text):
    if not text or text == "No synopsis available." or text == "No description available.":
        return "Aucune description disponible."

    print(f"🔄 Tentative de traduction: {text[:50]}...")

    # Traductions basiques pour les termes courts
    basic_translations = {
        "Unknown": "Inconnu",
        "Completed": "Terminé", 
        "Ongoing": "En cours",
        "Finished Airing": "Diffusion terminée",
        "Currently Airing": "En cours de diffusion",
        "Not yet aired": "Pas encore diffusé",
        "episodes": "épisodes",
        "episode": "épisode",
        "season": "saison",
        "movie": "film",
        "OVA": "OVA",
        "Special": "Spécial"
    }

    # Pour les textes longs (synopsis), essayer plusieurs APIs de traduction
    if len(text.split()) > 10:
        # Essayer d'abord LibreTranslate (API gratuite)
        try:
            url = "https://libretranslate.de/translate"
            data = {
                'q': text,
                'source': 'en',
                'target': 'fr',
                'format': 'text'
            }

            response = requests.post(url, data=data, timeout=15)
            result = response.json()

            if 'translatedText' in result:
                translated = result['translatedText']
                print(f"✅ Traduction LibreTranslate réussie: {translated[:50]}...")
                return translated

        except Exception as e:
            print(f"❌ Erreur LibreTranslate: {e}")

        # Essayer MyMemory en backup
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text[:500],  # Limiter la taille
                'langpair': 'en|fr'
            }

            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if data.get('responseStatus') == 200:
                translated = data['responseData']['translatedText']
                if translated and translated != text and "MYMEMORY WARNING" not in translated:
                    print(f"✅ Traduction MyMemory réussie: {translated[:50]}...")
                    return translated

        except Exception as e:
            print(f"❌ Erreur MyMemory: {e}")

        # Si toutes les APIs échouent, utiliser une traduction manuelle pour les termes communs
        print("⚠️ APIs de traduction échouées, utilisation de la traduction manuelle...")

        # Traductions manuelles pour les phrases communes d'anime
        manual_translations = {
            "Moments before": "Quelques instants avant",
            "birth": "naissance",
            "huge demon": "énorme démon",
            "known as": "connu sous le nom de",
            "attacked": "a attaqué",
            "wreaked havoc": "a semé le chaos",
            "In order to": "Afin de",
            "put an end": "mettre fin",
            "rampage": "saccage",
            "leader": "dirigeant",
            "village": "village",
            "sacrificed": "a sacrifié",
            "sealed": "a scellé",
            "monstrous beast": "bête monstrueuse",
            "inside": "à l'intérieur de",
            "newborn": "nouveau-né",
            "In the present": "À l'heure actuelle",
            "hyperactive": "hyperactif",
            "knuckle-headed": "têtu",
            "ninja": "ninja",
            "growing up": "grandissant",
            "Shunned because": "Rejeté à cause",
            "struggles": "lutte",
            "find his place": "trouver sa place",
            "burning desire": "désir ardent",
            "become": "devenir",
            "acknowledged": "reconnu",
            "villagers": "villageois",
            "despise": "méprisent",
            "However": "Cependant",
            "while": "tandis que",
            "goal": "objectif",
            "leads him": "le mène",
            "unbreakable bonds": "liens incassables",
            "lifelong friends": "amis de toujours",
            "lands him": "le place",
            "crosshairs": "ligne de mire",
            "deadly foes": "ennemis mortels",
            "Hidden Leaf Village": "Village Caché de la Feuille"
        }

        french_text = text
        for eng, fr in manual_translations.items():
            french_text = french_text.replace(eng, fr)

        # Appliquer aussi les traductions basiques
        for eng, fr in basic_translations.items():
            french_text = french_text.replace(eng, fr)

        return french_text

    # Pour les textes courts, utiliser seulement les traductions basiques
    french_text = text
    for eng, fr in basic_translations.items():
        french_text = french_text.replace(eng, fr)

    return french_text

# 🔍 Recherche via Jikan API
def search_anime(query):
    url = f"https://api.jikan.moe/v4/anime?q={query}&limit=1"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            anime = data['data'][0]

            # Récupérer les informations
            title = anime.get('title', 'Inconnu')
            synopsis = anime.get('synopsis', 'Aucune description disponible.')
            status = anime.get('status', 'Inconnu')

            # Traduire TOUT en français
            print(f"🔄 Traduction du synopsis pour: {title}")
            synopsis_fr = translate_to_french(synopsis)
            status_fr = translate_to_french(status)

            # Limiter la description pour Telegram
            if len(synopsis_fr) > 800:
                synopsis_fr = synopsis_fr[:800] + "..."

            return {
                'title': title,
                'synopsis': synopsis_fr,
                'image_url': anime['images']['jpg']['large_image_url'],
                'trailer_url': anime['trailer']['url'] if anime.get('trailer') else None,
                'score': anime.get('score', 'N/A'),
                'episodes': anime.get('episodes', 'N/A'),
                'status': status_fr
            }
    except Exception as e:
        print("Erreur lors de la recherche :", e)
    return None

# 🏠 Commande /start
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats["utilisateurs_uniques"].add(user_id)

    keyboard = [
        [InlineKeyboardButton("🔍 Rechercher un anime", callback_data="search_anime")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🌟 <b>Bienvenue sur AnimeBot !</b> 🌟\n\n"
        "🤖 <b>Description :</b>\n"
        "Je suis un bot intelligent qui vous aide à découvrir des animes incroyables ! Je fonctionne aussi bien en privé que dans les groupes.\n\n"
        "✨ <b>Fonctionnalités :</b>\n"
        "• 🔍 Recherche d'animes avec descriptions en français\n"
        "• 📝 Synopsis détaillés et traduits\n"
        "• 🎬 Liens vers les trailers\n"
        "• 👥 Fonctionne dans les groupes (envoyez juste le nom d'un anime)\n\n"
        "💡 <b>Comment utiliser :</b>\n"
        "• En privé : Utilisez les boutons ou <code>/anime nom_anime</code>\n"
        "• En groupe : Écrivez simplement le nom d'un anime\n\n"
        "Choisissez une option ci-dessous :",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

# 📌 /anime commande
async def anime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(
            "❌ <b>Utilisation incorrecte</b>\n\n"
            "Utilisez : <code>/anime nom_de_l_anime</code>\n\n"
            "Exemple : <code>/anime Naruto</code>",
            parse_mode="HTML"
        )

    query = " ".join(context.args)
    user_id = update.effective_user.id

    # Mise à jour des statistiques
    stats["recherches_total"] += 1
    stats["utilisateurs_uniques"].add(user_id)
    stats["derniere_recherche"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    await update.message.reply_text("🔎 <b>Recherche en cours...</b>", parse_mode="HTML")

    result = search_anime(query)
    if not result:
        return await update.message.reply_text(
            "❌ <b>Aucun résultat trouvé</b>\n\n"
            f"Désolé, je n'ai pas trouvé d'anime correspondant à : <i>{query}</i>\n\n"
            "💡 <b>Conseils :</b>\n"
            "• Vérifiez l'orthographe\n"
            "• Essayez avec le titre en anglais\n"
            "• Utilisez des mots-clés plus simples",
            parse_mode="HTML"
        )

    stats["anime_trouves"] += 1

    title = result['title']
    synopsis = result['synopsis']
    image_url = result['image_url']
    trailer_url = result['trailer_url']
    score = result['score']
    episodes = result['episodes']
    status = translate_to_french(result['status'])

    caption = (
        f"📺 <b>{title}</b>\n\n"
        f"⭐ <b>Note :</b> {score}/10\n"
        f"📹 <b>Épisodes :</b> {episodes}\n"
        f"📊 <b>Statut :</b> {status}\n\n"
        f"📝 <b>Synopsis :</b>\n{synopsis}"
    )

    # 🎬 Boutons
    buttons = []
    if trailer_url:
        buttons.append([InlineKeyboardButton("🎬 Voir le trailer", url=trailer_url)])
    buttons.append([InlineKeyboardButton("🔍 Nouvelle recherche", callback_data="search_anime")])

    # 🖼️ Envoyer l'image avec informations
    await update.message.reply_photo(
        photo=image_url,
        caption=caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    # 🎞️ Fichier local si disponible
    filename = os.path.join(VIDEO_FOLDER, f"{query.lower().replace(' ', '_')}.mp4")
    if os.path.isfile(filename):
        with open(filename, "rb") as vid:
            await update.message.reply_video(
                video=InputFile(vid), 
                caption="🎬 <b>Trailer local disponible</b>",
                parse_mode="HTML"
            )

# 📢 Commande de diffusion
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé. Permissions administrateur requises.")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ <b>Utilisation incorrecte</b>\n\n"
            "Utilisez : <code>/broadcast votre_message</code>",
            parse_mode="HTML"
        )
        return

    message = " ".join(context.args)
    users_list = list(stats["utilisateurs_uniques"])
    sent_count = 0
    failed_count = 0

    await update.message.reply_text(
        f"📢 <b>Diffusion en cours...</b>\n\n"
        f"👥 <b>Utilisateurs ciblés :</b> {len(users_list)}",
        parse_mode="HTML"
    )

    for user_id_target in users_list:
        if not is_banned(user_id_target):
            try:
                await context.bot.send_message(
                    chat_id=user_id_target,
                    text=f"📢 <b>Message des administrateurs</b>\n\n{message}",
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Erreur envoi à {user_id_target}: {e}")

    await update.message.reply_text(
        f"📢 <b>Diffusion terminée</b>\n\n"
        f"✅ <b>Envoyés :</b> {sent_count}\n"
        f"❌ <b>Échecs :</b> {failed_count}",
        parse_mode="HTML"
    )

# 📺 Commande d'ajout d'anime
async def add_anime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé. Permissions administrateur requises.")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ <b>Utilisation incorrecte</b>\n\n"
            "Utilisez : <code>/add_anime titre|synopsis|note|episodes|statut</code>\n\n"
            "Exemple :\n"
            "<code>/add_anime Mon Hero Academia|Un anime sur des super-héros|9.5|150|En cours</code>",
            parse_mode="HTML"
        )
        return

    anime_data = " ".join(context.args).split("|")

    if len(anime_data) != 5:
        await update.message.reply_text(
            "❌ <b>Format incorrect</b>\n\n"
            "Format requis : <code>titre|synopsis|note|episodes|statut</code>",
            parse_mode="HTML"
        )
        return

    title, synopsis, score, episodes, status = anime_data

    # Ajouter à la base locale
    anime_key = title.lower().replace(" ", "_")
    anime_database[anime_key] = {
        'title': title.strip(),
        'synopsis': synopsis.strip(),
        'score': score.strip(),
        'episodes': episodes.strip(),
        'status': status.strip(),
        'image_url': 'https://via.placeholder.com/400x600/333/fff?text=Anime+Local',
        'trailer_url': None,
        'source': 'local'
    }

    await update.message.reply_text(
        f"✅ <b>Anime ajouté avec succès !</b>\n\n"
        f"📺 <b>Titre :</b> {title}\n"
        f"📝 <b>Synopsis :</b> {synopsis[:100]}...\n"
        f"⭐ <b>Note :</b> {score}\n"
        f"📹 <b>Épisodes :</b> {episodes}\n"
        f"📊 <b>Statut :</b> {status}\n\n"
        f"🗃️ <b>Base locale :</b> {len(anime_database)} animes",
        parse_mode="HTML"
    )

# 👥 Commandes de gestion des utilisateurs
async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé.")
        return

    if not context.args:
        await update.message.reply_text("❌ Utilisez : <code>/add_admin user_id</code>", parse_mode="HTML")
        return

    try:
        target_user_id = int(context.args[0])
        admins.add(target_user_id)
        await update.message.reply_text(f"✅ Utilisateur {target_user_id} ajouté aux admins.")
    except ValueError:
        await update.message.reply_text("❌ ID utilisateur invalide.")

async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé.")
        return

    if not context.args:
        await update.message.reply_text("❌ Utilisez : <code>/ban user_id</code>", parse_mode="HTML")
        return

    try:
        target_user_id = int(context.args[0])
        banned_users.add(target_user_id)
        await update.message.reply_text(f"🚫 Utilisateur {target_user_id} banni.")
    except ValueError:
        await update.message.reply_text("❌ ID utilisateur invalide.")

async def unban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé.")
        return

    if not context.args:
        await update.message.reply_text("❌ Utilisez : <code>/unban user_id</code>", parse_mode="HTML")
        return

    try:
        target_user_id = int(context.args[0])
        banned_users.discard(target_user_id)
        await update.message.reply_text(f"✅ Utilisateur {target_user_id} débanni.")
    except ValueError:
        await update.message.reply_text("❌ ID utilisateur invalide.")

async def list_admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé.")
        return

    admin_list = "\n".join([f"• {admin_id}" for admin_id in admins])
    await update.message.reply_text(
        f"🛡️ <b>Liste des administrateurs</b>\n\n{admin_list}",
        parse_mode="HTML"
    )

# 🛠️ Commande /admin
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Accès refusé. Permissions administrateur requises.")
        return

    admin_keyboard = [
        [InlineKeyboardButton("📊 Statistiques détaillées", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Diffusion message", callback_data="broadcast_info")],
        [InlineKeyboardButton("📝 Ajouter anime", callback_data="add_anime_info")],
        [InlineKeyboardButton("👥 Gestion utilisateurs", callback_data="user_management")],
        [InlineKeyboardButton("🗃️ Base de données", callback_data="database_info")]
    ]

    await update.message.reply_text(
        "🛠️ <b>Panneau d'Administration</b>\n\n"
        f"👋 Bienvenue admin #{user_id}\n\n"
        "📊 <b>Résumé rapide :</b>\n"
        f"• Utilisateurs : {len(stats['utilisateurs_uniques'])}\n"
        f"• Recherches : {stats['recherches_total']}\n"
        f"• Animes locaux : {len(anime_database)}\n"
        f"• Admins : {len(admins)}\n"
        f"• Bannis : {len(banned_users)}\n\n"
        "Choisissez une action :",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(admin_keyboard)
    )

# 🔄 Gestionnaire de callbacks
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if query.data == "search_anime":
        await query.edit_message_text(
            "🔍 <b>Recherche d'anime</b>\n\n"
            "Pour rechercher un anime, utilisez la commande :\n"
            "<code>/anime nom_de_l_anime</code>\n\n"
            "Exemple : <code>/anime Attack on Titan</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Retour au menu", callback_data="back_to_start")
            ]])
        )

    elif query.data == "stats":
        stats_text = (
            "📊 <b>Statistiques du bot</b>\n\n"
            f"🔍 <b>Recherches totales :</b> {stats['recherches_total']}\n"
            f"✅ <b>Animes trouvés :</b> {stats['anime_trouves']}\n"
            f"👥 <b>Utilisateurs uniques :</b> {len(stats['utilisateurs_uniques'])}\n"
            f"🕐 <b>Dernière recherche :</b> {stats['derniere_recherche'] or 'Aucune'}\n\n"
            f"📈 <b>Taux de réussite :</b> {(stats['anime_trouves']/max(stats['recherches_total'], 1)*100):.1f}%"
        )

        await query.edit_message_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Retour au menu", callback_data="back_to_start")
            ]])
        )

    elif query.data == "admin_panel" and is_admin(user_id):
        admin_keyboard = [
            [InlineKeyboardButton("📊 Statistiques détaillées", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 Diffusion message", callback_data="broadcast")],
            [InlineKeyboardButton("📝 Ajouter anime local", callback_data="add_anime")],
            [InlineKeyboardButton("🏠 Retour au menu", callback_data="back_to_start")]
        ]

        await query.edit_message_text(
            "🛠️ <b>Panneau d'Administration</b>\n\n"
            "Choisissez une action :",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )

    elif query.data == "admin_stats" and is_admin(user_id):
        users_list = list(stats["utilisateurs_uniques"])
        detailed_stats = (
            "📊 <b>Statistiques Administrateur</b>\n\n"
            f"🔍 <b>Recherches totales :</b> {stats['recherches_total']}\n"
            f"✅ <b>Animes trouvés :</b> {stats['anime_trouves']}\n"
            f"❌ <b>Recherches échouées :</b> {stats['recherches_total'] - stats['anime_trouves']}\n"
            f"👥 <b>Utilisateurs uniques :</b> {len(stats['utilisateurs_uniques'])}\n"
            f"🕐 <b>Dernière recherche :</b> {stats['derniere_recherche'] or 'Aucune'}\n\n"
            f"📈 <b>Taux de réussite :</b> {(stats['anime_trouves']/max(stats['recherches_total'], 1)*100):.1f}%\n"
            f"📅 <b>Bot démarré :</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

        await query.edit_message_text(
            detailed_stats,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🛠️ Retour admin", callback_data="admin_panel")
            ]])
        )

    elif query.data == "broadcast_info" and is_admin(user_id):
        await query.edit_message_text(
            "📢 <b>Diffusion de message</b>\n\n"
            "Pour diffuser un message à tous les utilisateurs :\n"
            "<code>/broadcast votre_message</code>\n\n"
            "Exemple :\n"
            "<code>/broadcast Mise à jour du bot ! Nouvelles fonctionnalités disponibles.</code>\n\n"
            f"👥 <b>Utilisateurs ciblés :</b> {len(stats['utilisateurs_uniques'])}\n"
            f"🚫 <b>Utilisateurs bannis :</b> {len(banned_users)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Retour admin", callback_data="admin_back")
            ]])
        )

    elif query.data == "add_anime_info" and is_admin(user_id):
        await query.edit_message_text(
            "📝 <b>Ajouter un anime manuellement</b>\n\n"
            "Pour ajouter un anime à la base locale :\n"
            "<code>/add_anime titre|synopsis|note|episodes|statut</code>\n\n"
            "Exemple :\n"
            "<code>/add_anime One Piece|L'histoire de Luffy qui veut devenir roi des pirates|9.2|1000+|En cours</code>\n\n"
            f"🗃️ <b>Animes en base :</b> {len(anime_database)}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Retour admin", callback_data="admin_back")
            ]])
        )

    elif query.data == "user_management" and is_admin(user_id):
        await query.edit_message_text(
            "👥 <b>Gestion des utilisateurs</b>\n\n"
            "Commandes disponibles :\n\n"
            "🛡️ <b>Gestion des admins :</b>\n"
            "• <code>/add_admin user_id</code> - Ajouter un admin\n"
            "• <code>/list_admins</code> - Voir la liste des admins\n\n"
            "🚫 <b>Gestion des bans :</b>\n"
            "• <code>/ban user_id</code> - Bannir un utilisateur\n"
            "• <code>/unban user_id</code> - Débannir un utilisateur\n\n"
            f"📊 <b>Statistiques :</b>\n"
            f"• Admins : {len(admins)}\n"
            f"• Bannis : {len(banned_users)}\n"
            f"• Utilisateurs actifs : {len(stats['utilisateurs_uniques'])}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Retour admin", callback_data="admin_back")
            ]])
        )

    elif query.data == "database_info" and is_admin(user_id):
        await query.edit_message_text(
            "🗃️ <b>Base de données</b>\n\n"
            f"📺 <b>Animes locaux :</b> {len(anime_database)}\n"
            f"🔍 <b>Recherches totales :</b> {stats['recherches_total']}\n"
            f"✅ <b>Animes trouvés :</b> {stats['anime_trouves']}\n"
            f"📈 <b>Taux de réussite :</b> {(stats['anime_trouves']/max(stats['recherches_total'], 1)*100):.1f}%\n\n"
            "💾 <b>Données stockées :</b>\n"
            "• Statistiques d'utilisation\n"
            "• Liste des admins\n"
            "• Utilisateurs bannis\n"
            "• Animes ajoutés manuellement",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Retour admin", callback_data="admin_back")
            ]])
        )

    elif query.data == "admin_back" and is_admin(user_id):
        # Retour au panneau admin principal
        admin_keyboard = [
            [InlineKeyboardButton("📊 Statistiques détaillées", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 Diffusion message", callback_data="broadcast_info")],
            [InlineKeyboardButton("📝 Ajouter anime", callback_data="add_anime_info")],
            [InlineKeyboardButton("👥 Gestion utilisateurs", callback_data="user_management")],
            [InlineKeyboardButton("🗃️ Base de données", callback_data="database_info")]
        ]

        await query.edit_message_text(
            "🛠️ <b>Panneau d'Administration</b>\n\n"
            f"👋 Bienvenue admin #{user_id}\n\n"
            "📊 <b>Résumé rapide :</b>\n"
            f"• Utilisateurs : {len(stats['utilisateurs_uniques'])}\n"
            f"• Recherches : {stats['recherches_total']}\n"
            f"• Animes locaux : {len(anime_database)}\n"
            f"• Admins : {len(admins)}\n"
            f"• Bannis : {len(banned_users)}\n\n"
            "Choisissez une action :",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )

    elif query.data == "back_to_start":
        keyboard = [
            [InlineKeyboardButton("🔍 Rechercher un anime", callback_data="search_anime")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🌟 <b>Bienvenue sur AnimeBot !</b> 🌟\n\n"
            "🤖 <b>Description :</b>\n"
            "Je suis un bot intelligent qui vous aide à découvrir des animes incroyables ! Je fonctionne aussi bien en privé que dans les groupes.\n\n"
            "✨ <b>Fonctionnalités :</b>\n"
            "• 🔍 Recherche d'animes avec descriptions en français\n"
            "• 📝 Synopsis détaillés et traduits\n"
            "• 🎬 Liens vers les trailers\n"
            "• 👥 Fonctionne dans les groupes (envoyez juste le nom d'un anime)\n\n"
            "💡 <b>Comment utiliser :</b>\n"
            "• En privé : Utilisez les boutons ou <code>/anime nom_anime</code>\n"
            "• En groupe : Écrivez simplement le nom d'un anime\n\n"
            "Choisissez une option ci-dessous :",
            parse_mode="HTML",
            reply_markup=reply_markup
        )

# 👥 Gestionnaire de messages dans les groupes
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Vérifier si c'est un groupe/supergroupe
    if update.effective_chat.type not in ['group', 'supergroup']:
        return

    # Vérifier si le bot est admin du groupe
    try:
        bot_member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            return
    except:
        return

    message_text = update.message.text.strip()

    # Détecter si c'est potentiellement un nom d'anime (pas de commande, pas trop long)
    if len(message_text) < 50 and not message_text.startswith('/'):
        # Rechercher l'anime
        result = search_anime(message_text)

        if result:
            # Mise à jour des statistiques
            stats["recherches_total"] += 1
            stats["utilisateurs_uniques"].add(update.effective_user.id)
            stats["derniere_recherche"] = datetime.now().strftime("%d/%m/%Y %H:%M")
            stats["anime_trouves"] += 1

            title = result['title']
            synopsis = result['synopsis']
            image_url = result['image_url']
            trailer_url = result['trailer_url']
            score = result['score']
            episodes = result['episodes']
            status = translate_to_french(result['status'])

            caption = (
                f"📺 <b>{title}</b>\n\n"
                f"⭐ <b>Note :</b> {score}/10\n"
                f"📹 <b>Épisodes :</b> {episodes}\n"
                f"📊 <b>Statut :</b> {status}\n\n"
                f"📝 <b>Synopsis :</b>\n{synopsis}"
            )

            # 🎬 Boutons pour les groupes
            buttons = []
            if trailer_url:
                buttons.append([InlineKeyboardButton("🎬 Voir le trailer", url=trailer_url)])

            # 🖼️ Envoyer l'image avec informations
            await update.message.reply_photo(
                photo=image_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )

            # 🎞️ Fichier local si disponible
            filename = os.path.join(VIDEO_FOLDER, f"{message_text.lower().replace(' ', '_')}.mp4")
            if os.path.isfile(filename):
                with open(filename, "rb") as vid:
                    await update.message.reply_video(
                        video=InputFile(vid), 
                        caption="🎬 <b>Trailer local disponible</b>",
                        parse_mode="HTML"
                    )

# ▶️ Lancer le bot
def main():
    app = Application.builder().token(API_TOKEN).build()

    # Commandes
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("anime", anime_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("add_anime", add_anime_cmd))
    app.add_handler(CommandHandler("add_admin", add_admin_cmd))
    app.add_handler(CommandHandler("ban", ban_user_cmd))
    app.add_handler(CommandHandler("unban", unban_user_cmd))
    app.add_handler(CommandHandler("list_admins", list_admins_cmd))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Messages dans les groupes
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))

    print("🤖 Bot AnimeBot lancé en français !")
    app.run_polling()

if __name__ == "__main__":
    main()