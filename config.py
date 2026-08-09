import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente (il token)
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- ID REALI ---
REVIEW_CHANNEL_ID = 1535055543033532467  #verification-chat
UPDATES_CHANNEL_ID = 1092204135505461349  #wrs-updated
SUBMISSION_CHANNEL_ID = 1300032038165938176  #pb-share

DATABASE_CHANNEL_ID = 1252593722286276680  #feargames-wrs
SIM_WR_CHANNEL_ID = 1252708706173325342  #sim-wrs
RANKINGS_CHANNEL_ID = 1252708822359871620  #rankings 
REJECT_CHANNEL_ID = 1536101024832430251 #rejected-screens
ADMIN_ID = 715247279141027890
MIO_ID = 715247279141027890

# --- SISTEMA DEGLI ALIAS ---
ALIASES = {
    "namsarr1": "namsar",
    "samu_onchill": "boxato" # Ricorda di mettere sempre la chiave in minuscolo!
}

# --- IMPOSTAZIONI WEBHOOK TORNEI ---
WEBHOOK_URL = "https://discord.com/api/webhooks/1536128543736463522/Kg_nR_IqBvpeMxatz7s6qtFLgi6Y6VRKJQj2UOzxUNLn-DT-paIYQdnoAK3FNEqov33z"
TOURNEY_MESSAGE_ID = 1536138120871936071