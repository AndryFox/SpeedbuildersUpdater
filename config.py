import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente (il token)
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- ID PER TEST ---
REVIEW_CHANNEL_ID = 1535055543033532467  #verification-chat
UPDATES_CHANNEL_ID = 1535055543033532467  #sostituto di #wrs-updated
SUBMISSION_CHANNEL_ID = 1535055543033532467  #sostituto di #pb-share
DATABASE_CHANNEL_ID = 1252593722286276680  #feargames-wrs
SIM_WR_CHANNEL_ID = 1252708706173325342  #sim-wrs
RANKINGS_CHANNEL_ID = 1252708822359871620  #rankings 
ADMIN_ID = 715247279141027890
MIO_ID = 715247279141027890

# --- SISTEMA DEGLI ALIAS ---
ALIASES = {
    "namsarr1": "namsar",
    "samu_onchill": "boxato" # Ricorda di mettere sempre la chiave in minuscolo!
}