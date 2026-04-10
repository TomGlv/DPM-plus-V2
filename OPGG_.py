import requests
import os
import time

# Configuration
API_KEY = os.getenv("RIOT_KEY")
WEBHOOK = os.getenv("WEBHOOK")
GAME_NAME = "DembouzPartouz"
TAG_LINE = "669"
REGION = "europe"
PLATFORM = "euw1"
FILE_NAME = "last_match.txt"

def get_data(url):
    headers = {"X-Riot-Token": API_KEY}
    res = requests.get(url, headers=headers)
    return res.json() if res.status_code == 200 else None

def calculate_master_distance(tier, rank, lp):
    ranks = {"IV": 300, "III": 200, "II": 100, "I": 0}
    if tier != "DIAMOND": return "Calcul Diamond uniquement"
    lp_to_master = ranks.get(rank, 0) + (100 - lp)
    wins_needed = -(-lp_to_master // 20)
    return f"{lp_to_master} LP ({wins_needed} net wins)"

def main():
    acc = get_data(f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}")
    if not acc: return
    puuid = acc['puuid']

    # On récupère les 3 DERNIERS MATCHS au cas où tu as enchaîné
    m_list = get_data(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=3")
    if not m_list: return

    # Lire le dernier match envoyé
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "r") as f:
            saved_id = f.read().strip()
    else:
        saved_id = ""

    # Inverser la liste pour envoyer le plus vieux match en premier (ordre chronologique)
    m_list.reverse()

    new_last_id = saved_id
    found_new = False

    for match_id in m_list:
        if match_id == saved_id or (saved_id != "" and match_id < saved_id):
            continue # Déjà envoyé ou plus vieux

        # Si on est ici, c'est un nouveau match
        found_new = True
        game = get_data(f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}")
        rank_info = get_data(f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}")

        if game and rank_info:
            p = next(pl for pl in game['info']['participants'] if pl['puuid'] == puuid)
            solo = next((i for i in rank_info if i['queueType'] == "RANKED_SOLO_5x5"), {"tier": "UNRANKED", "rank": "", "leaguePoints": 0})
            
            dist_master = calculate_master_distance(solo['tier'], solo['rank'], solo['leaguePoints'])
            duration = game['info']['gameDuration']
            cs = p['totalMinionsKilled'] + p['neutralMinionsKilled']
            cs_min = round(cs / (duration / 60), 1)
            team_kills = sum(pl['kills'] for pl in game['info']['participants'] if pl['teamId'] == p['teamId'])
            kp = round(((p['kills'] + p['assists']) / max(1, team_kills)) * 100, 1)
            champ_img = f"https://ddragon.leagueoflegends.com/cdn/14.7.1/img/champion/{p['championName']}.png"

            embed = {
                "embeds": [{
                    "author": {"name": f"PERFORMANCE ANALYSIS | {p['championName'].upper()}", "icon_url": champ_img},
                    "title": f"{'🟩 WIN' if p['win'] else '🟥 LOSS'} - {int(duration//60)}m {int(duration%60)}s",
                    "color": 0x2ecc71 if p['win'] else 0xe74c3c,
                    "thumbnail": {"url": champ_img},
                    "fields": [
                        {"name": "🛡️ RANKED STATUS", "value": f"**Tier**: {solo['tier']} {solo['rank']}\n**LPs**: {solo['leaguePoints']} LP", "inline": True},
                        {"name": "🏆 ROAD TO MASTER", "value": f"**Missing**: {dist_master}", "inline": True},
                        {"name": "⚔️ COMBAT", "value": f"**KDA**: {p['kills']}/{p['deaths']}/{p['assists']}\n**KP**: {kp}%", "inline": True},
                        {"name": "💰 ECONOMY", "value": f"**CS**: {cs} ({cs_min}/m)\n**Damage**: {p['totalDamageDealtToChampions']}", "inline": True}
                    ],
                    "footer": {"text": f"DembouzPartouz • {match_id}"},
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                }]
            }
            if requests.post(WEBHOOK, json=embed).status_code in [200, 204]:
                new_last_id = match_id
                time.sleep(2) # Petite pause pour Discord

    # Sauvegarder le tout dernier match traité
    if found_new:
        with open(FILE_NAME, "w") as f:
            f.write(new_last_id)
        print(f"Mémoire mise à jour : {new_last_id}")

if __name__ == "__main__":
    main()
