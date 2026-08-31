import streamlit as st
import statsapi
import requests
import datetime
import pandas as pd

# --- CONFIGURATION & CSS STYLING ---
st.set_page_config(page_title="MLB Trend Tracker", layout="wide")
CURRENT_SEASON = 2026 # Update this based on the current season

# Custom CSS for absolute vertical centering and freezing table size below 768px
st.markdown("""
    <style>
        /* Add clean separation between section titles and tables */
        h3 {
            margin-top: 8px !important;
            margin-bottom: 8px !important;
        }
        
        /* --- FORCE HORIZONTAL SCROLL & RESPONSIVE RULES --- */
        .block-container {
            max-width: 100% !important;
        }
        
        /* Rules applied ONLY when screen width is less than 768px */
        @media (max-width: 640px) {
            .stMainBlockContainer, [data-testid="stMainBlockContainer"] {
                overflow-x: auto !important;
                max-width: 640px !important;
            }
            
/*            [data-testid="stHorizontalBlock"] {
                min-width: 50px !important;
                max-width: 100px !important;
            }*/

            .stMainBlockContainer [data-testid="stHorizontalBlock"] > div:not(:nth-child(2)) {
                flex: 0 0 70px !important;
                min-width: 70px !important;
                max-width: 70px !important;
                width: 70px !important;
            }
            .stMainBlockContainer [data-testid="stHorizontalBlock"] > div:nth-child(2) {
                flex: 0 0 170px !important;
                min-width: 70px !important;
                max-width: 170px !important;
                width: 170px !important;
            }
        }

        /* Prevent Streamlit columns from stacking vertically on larger screens */
        [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 0.4rem !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
        }

        /* Default rule for all columns */
        [data-testid="column"] {
            flex: 1 0 auto !important;
            min-width: 60px !important;
            display: flex;
            align-items: center;
        }

        /* --- ABSOLUTE VERTICAL ALIGNMENT FIX FOR BUTTONS VS TEXT --- */
        div[data-testid="stMarkdownContainer"] {
            width: 100%;
        }

        /* Remove margins from text elements to ensure precise centering */
        p, div[data-testid="stMarkdownContainer"] > p {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
            line-height: 1.2 !important;
        }

        /* Force button wrapper to match text alignment baseline */
        [data-testid="stButton"] {
            display: flex;
            align-items: center;
            height: 100%;
        }

        /* Make the Stats buttons compact to match text row height */
        [data-testid="stButton"] button {
            padding: 0px 6px !important;
            min-height: 22px !important;
            height: 28px !important;
            font-size: 0.8rem !important;
            line-height: normal !important;
        }

        /* Tighten divider spacing */
        hr {
            margin-top: 2px !important;
            margin-bottom: 4px !important;
            min-width: 530px !important
        }
    </style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def fmt_rate(val):
    """Formats rate stats (AVG, OBP, SLG, OPS, BABIP) to drop the leading zero: .XXX"""
    try:
        v = float(val)
        f = f"{v:.3f}"
        if f.startswith("0."): return f[1:]
        if f.startswith("-0."): return "-" + f[2:]
        return f
    except:
        return ".000"

def fmt_pct(num, den):
    """Formats percentages as XX.X%"""
    try:
        if not den or int(den) == 0:
            return "0.0%"
        return f"{(float(num) / float(den)) * 100:.1f}%"
    except:
        return "0.0%"

def calculate_batter_trend(season_ops, recent_ops):
    diff = recent_ops - season_ops
    if diff >= 0.100: return "⬆️🔥"
    elif diff >= 0.050: return "↗️🚀"
    elif diff > -0.050: return "➡️👍"
    elif diff <= -0.100: return "⬇️🥶"
    else: return "↘️🧊"

def calculate_pitcher_trend(season_era, recent_era):
    diff = recent_era - season_era
    if diff <= -2.00: return "⬆️🔥"
    elif diff <= -1.00: return "↗️🚀"
    elif diff < 1.00: return "➡️👍"
    elif diff >= 2.00: return "⬇️🥶"
    else: return "↘️🧊"

def ip_to_outs(ip_val):
    if not ip_val: return 0
    ip_float = float(ip_val)
    full_innings = int(ip_float)
    partial = round((ip_float - full_innings) * 10)
    return (full_innings * 3) + partial

def outs_to_ip(outs):
    full = outs // 3
    partial = outs % 3
    return float(f"{full}.{partial}")

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_daily_schedule(date_str):
    return statsapi.schedule(date=date_str)

@st.cache_data(ttl=3600)
def get_game_data(game_id):
    return statsapi.boxscore_data(game_id)

@st.cache_data(ttl=43200)
def fetch_player_season_stats(player_id, group="hitting", season=CURRENT_SEASON):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group={group}&season={season}"
    resp = requests.get(url).json()
    if 'stats' in resp and resp['stats'] and resp['stats'][0]['splits']:
        return resp['stats'][0]['splits'][0]['stat']
    return {}

@st.cache_data(ttl=43200)
def fetch_player_game_logs(player_id, group="hitting", season=CURRENT_SEASON):
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group={group}&season={season}"
    resp = requests.get(url).json()
    if 'stats' in resp and resp['stats']:
        logs = resp['stats'][0]['splits']
        logs.reverse() # Newest games first
        return logs
    return []

@st.cache_data(ttl=43200)
def get_player_attributes(player_id):
    """Fetches batting and pitching side directly from the person endpoint"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
    resp = requests.get(url).json()
    if 'people' in resp and resp['people']:
        p = resp['people'][0]
        return {
            'batSide': p.get('batSide', {}).get('code', 'R'),
            'pitchHand': p.get('pitchHand', {}).get('code', 'R')
        }
    return {'batSide': 'R', 'pitchHand': 'R'}

# --- LOCAL DATA PROCESSING (NO CACHE) ---
def calculate_trailing_batter_stats(game_logs, limit_type, limit_val, target_date):
    if not game_logs: return {}
    
    totals = {'atBats': 0, 'plateAppearances': 0, 'hits': 0, 'doubles': 0, 
              'triples': 0, 'homeRuns': 0, 'baseOnBalls': 0, 'strikeOuts': 0,
              'runs': 0, 'rbi': 0, 'stolenBases': 0, 'caughtStealing': 0, 'sacFlies': 0}
    
    games_counted = 0
    pa_counted = 0
    cutoff_date = target_date - datetime.timedelta(days=limit_val)
    
    for log in game_logs:
        log_date = datetime.datetime.strptime(log['date'], "%Y-%m-%d").date()
        
        if log_date > target_date: 
            continue
            
        if limit_type == "Last N days" and log_date < cutoff_date:
            break
            
        stat = log['stat']
        if limit_type == "Last N plate appearances" and pa_counted >= limit_val: break
        if limit_type == "Last N games" and games_counted >= limit_val: break
        
        for key in totals:
            if key == 'sacFlies':
                totals['sacFlies'] += stat.get('sacFlies', 0) or stat.get('sacrificeFlies', 0)
            else:
                totals[key] += stat.get(key, 0)
            
        pa_counted += stat.get('plateAppearances', 0)
        games_counted += 1
        
    ab = totals['atBats']
    pa = totals['plateAppearances']
    hits = totals['hits']
    bb = totals['baseOnBalls']
    tb = hits + totals['doubles'] + (totals['triples'] * 2) + (totals['homeRuns'] * 3)
    
    totals.update({
        'gamesCounted': games_counted,
        'avg': hits / ab if ab > 0 else 0,
        'obp': (hits + bb) / pa if pa > 0 else 0,
        'slg': tb / ab if ab > 0 else 0,
        'ops': ((hits + bb) / pa) + (tb / ab) if pa > 0 and ab > 0 else 0
    })
    return totals

def calculate_trailing_pitcher_stats(game_logs, limit_type, limit_val, target_date):
    if not game_logs: return {}
    
    totals = {'outsPitched': 0, 'hits': 0, 'doubles': 0, 'triples': 0, 'baseOnBalls': 0, 
              'strikeOuts': 0, 'homeRuns': 0, 'earnedRuns': 0, 'runs': 0, 
              'battersFaced': 0, 'atBats': 0, 'hitByPitch': 0, 'sacFlies': 0}
    
    starts_counted = 0
    games_counted = 0
    cutoff_date = target_date - datetime.timedelta(days=limit_val)
    
    for log in game_logs:
        log_date = datetime.datetime.strptime(log['date'], "%Y-%m-%d").date()
        
        if log_date > target_date:
            continue
            
        if limit_type == "Last N days" and log_date < cutoff_date:
            break
            
        stat = log['stat']
        is_start = log.get('isStarter', False)
        outs_this_game = ip_to_outs(stat.get('inningsPitched', "0.0"))
        
        if limit_type == "Last N starts" and starts_counted >= limit_val: break
        if limit_type == "Last N innings pitched" and totals['outsPitched'] >= (limit_val * 3): break
        if limit_type == "Last N games" and games_counted >= limit_val: break
        
        for key in totals:
            if key == 'outsPitched': continue
            if key == 'hitByPitch':
                totals['hitByPitch'] += stat.get('hitByPitch', 0) or stat.get('hitBatsmen', 0)
            elif key == 'sacFlies':
                totals['sacFlies'] += stat.get('sacFlies', 0) or stat.get('sacrificeFlies', 0)
            else:
                totals[key] += stat.get(key, 0)
            
        totals['outsPitched'] += outs_this_game
        if is_start: starts_counted += 1
        games_counted += 1
        
    ip = outs_to_ip(totals['outsPitched'])
    er = totals['earnedRuns']
    ab = totals['atBats']
    hits = totals['hits']
    bb = totals['baseOnBalls']
    hbp = totals['hitByPitch']
    hr = totals['homeRuns']
    k = totals['strikeOuts']
    bf = totals['battersFaced']
    tb = hits + totals['doubles'] + (totals['triples'] * 2) + (hr * 3)
    
    total_ip_calc = totals['outsPitched'] / 3.0
    era = (9 * er) / total_ip_calc if total_ip_calc > 0 else 0.00
    fip = (((13 * hr) + (3 * (bb + hbp)) - (2 * k)) / total_ip_calc + 3.083) if total_ip_calc > 0 else 0.00
    
    obpa = (hits + bb + hbp) / bf if bf > 0 else 0
    slga = tb / ab if ab > 0 else 0
    
    totals.update({
        'gamesCounted': games_counted,
        'inningsPitched': ip,
        'era': era,
        'fip': fip,
        'baa': hits / ab if ab > 0 else 0,
        'obpa': obpa,
        'slga': slga,
        'opsa': obpa + slga
    })
    return totals


# --- UI: DIALOG MODAL (POPUP) ---
@st.dialog("Complete Player Stats", width="large")
def show_stats_dialog(player_name, df):
    st.write(f"### {player_name}")
    st.dataframe(df, hide_index=True)


# --- UI: SIDEBAR ---
st.sidebar.header("Game Selection")
selected_date = st.sidebar.date_input("Select Date", datetime.date.today())
date_str = selected_date.strftime('%m/%d/%Y')

games = get_daily_schedule(date_str)
if not games:
    st.error("No games scheduled for this date.")
    st.stop()

game_options = {f"{g['away_name']} @ {g['home_name']}": g['game_id'] for g in games}
default_game_index = 0
for i, game_str in enumerate(game_options.keys()):
    if "Blue Jays" in game_str:
        default_game_index = i
        break

selected_game_name = st.sidebar.selectbox("Select Game", list(game_options.keys()), index=default_game_index)
game_id = game_options[selected_game_name]

st.sidebar.header("Timeframe Settings")

# Batters Inputs
st.sidebar.subheader("Batters")
batter_limit_type = st.sidebar.selectbox("Measure by:", ["Last N plate appearances", "Last N games", "Last N days"], index=0)
b_val_default = 100 if "plate" in batter_limit_type else (30 if "days" in batter_limit_type else 30)
batter_val = st.sidebar.number_input(f"Count ({batter_limit_type})", value=b_val_default)

# Starting Pitchers Inputs
st.sidebar.subheader("Starting Pitchers")
sp_limit_type = st.sidebar.selectbox("Measure SP by:", ["Last N starts", "Last N innings pitched", "Last N days"], index=1)
s_val_default = 5 if "starts" in sp_limit_type else (30 if "days" in sp_limit_type else 36)
sp_val = st.sidebar.number_input(f"Count ({sp_limit_type})", value=s_val_default)

# Relief Pitchers Inputs
st.sidebar.subheader("Relief Pitchers")
rp_limit_type = st.sidebar.selectbox("Measure RP by:", ["Last N games", "Last N innings pitched", "Last N days"], index=0)
r_val_default = 10 if "games" in rp_limit_type else (30 if "days" in rp_limit_type else 9)
rp_val = st.sidebar.number_input(f"Count ({rp_limit_type})", value=r_val_default)


# --- FETCH GAME DATA ---
boxscore = get_game_data(game_id)

def get_player_info(team_dict, player_id):
    p_key = f"ID{player_id}"
    if p_key in team_dict['players']:
        p = team_dict['players'][p_key]
        attrs = get_player_attributes(player_id)
        return {
            "id": player_id,
            "name": p['person']['fullName'],
            "jersey": p.get('jerseyNumber', '00'),
            "def_pos": p.get('position', {}).get('abbreviation', 'PH'),
            "bat_side": attrs['batSide'],
            "pitch_hand": attrs['pitchHand']
        }
    return None


# --- UI: MAIN APP ---
st.title(f"Game Tracker: {selected_game_name}")

away_team, home_team = selected_game_name.split(" @ ")
team_list = [away_team, home_team]

default_team_idx = 0
for idx, t in enumerate(team_list):
    if "Blue Jays" in t:
        default_team_idx = idx
        break

selected_team = st.radio("Select Team", team_list, index=default_team_idx, horizontal=True, label_visibility="collapsed")

def render_batters(title, player_ids, team_data):
    st.subheader(title)
    
    batter_col_ratios = [1, 2, 1, 1, 1, 1]
#    batter_col_ratios = [0.3, 0.6, 1.4, 0.6, 0.6, 0.6, 0.6]
    
    cols = st.columns(batter_col_ratios, vertical_alignment="center")
#    cols[0].write("**#**")
    cols[0].write("**Pos (Bat)**")
#    cols[1].write("**Pos (Bat)**")
    cols[1].write("**Name**")
    cols[2].write("**sOPS**")
    cols[3].write("**rOPS**")
    cols[4].write("**Trend**")
    cols[5].write("**Detail**")
    st.divider()

    for i, pid in enumerate(player_ids):
        info = get_player_info(team_data, pid)
        if not info: continue
        
        season_stats = fetch_player_season_stats(pid, "hitting")
        game_logs = fetch_player_game_logs(pid, "hitting")
        recent_stats = calculate_trailing_batter_stats(game_logs, batter_limit_type, batter_val, selected_date)
        
        s_ops = float(season_stats.get('ops', 0))
        r_ops = float(recent_stats.get('ops', 0))
        
        cols = st.columns(batter_col_ratios, vertical_alignment="center")
        cols[0].write(str(i+1)+f" | {info['def_pos']} ({info['bat_side']})" if "Lineup" in title else f"{info['def_pos']} ({info['bat_side']})")
#        cols[1].write(f"{info['def_pos']} ({info['bat_side']})")
#        cols[2].write(f"#{info['jersey']} {info['name']}")
        cols[1].markdown(f'<div class="mobile-name-col">#{info["jersey"]} {info["name"]}</div>', unsafe_allow_html=True)
        cols[2].write(fmt_rate(s_ops))
        cols[3].write(fmt_rate(r_ops))
        cols[4].write(calculate_batter_trend(s_ops, r_ops))
        
        s_ab = season_stats.get('atBats', 0)
        s_pa = season_stats.get('plateAppearances', 0)
        s_h = season_stats.get('hits', 0)
        s_2b = season_stats.get('doubles', 0)
        s_3b = season_stats.get('triples', 0)
        s_hr = season_stats.get('homeRuns', 0)
        s_bb = season_stats.get('baseOnBalls', 0)
        s_k = season_stats.get('strikeOuts', 0)
        s_sb = season_stats.get('stolenBases', 0)
        s_cs = season_stats.get('caughtStealing', 0)
        s_sf = season_stats.get('sacFlies', 0) or season_stats.get('sacrificeFlies', 0)
        s_babip_den = s_ab - s_hr - s_k + s_sf
        s_babip = (s_h - s_hr) / s_babip_den if s_babip_den > 0 else 0.0
        
        r_ab = recent_stats.get('atBats', 0)
        r_pa = recent_stats.get('plateAppearances', 0)
        r_h = recent_stats.get('hits', 0)
        r_2b = recent_stats.get('doubles', 0)
        r_3b = recent_stats.get('triples', 0)
        r_hr = recent_stats.get('homeRuns', 0)
        r_bb = recent_stats.get('baseOnBalls', 0)
        r_k = recent_stats.get('strikeOuts', 0)
        r_sb = recent_stats.get('stolenBases', 0)
        r_cs = recent_stats.get('caughtStealing', 0)
        r_sf = recent_stats.get('sacFlies', 0)
        r_babip_den = r_ab - r_hr - r_k + r_sf
        r_babip = (r_h - r_hr) / r_babip_den if r_babip_den > 0 else 0.0
        
        df = pd.DataFrame([
            {
                "Split": "Season",
                "G": season_stats.get('gamesPlayed', 0),
                "PA": s_pa,
                "AVG": fmt_rate(season_stats.get('avg', 0)),
                "OBP": fmt_rate(season_stats.get('obp', 0)),
                "SLG": fmt_rate(season_stats.get('slg', 0)),
                "OPS": fmt_rate(s_ops),
                "H": s_h,
                "2B": s_2b,
                "3B": s_3b,
                "HR": s_hr,
                "BB": s_bb,
                "K": s_k,
                "HR %": fmt_pct(s_hr, s_pa),
                "XBH %": fmt_pct(s_2b + s_3b + s_hr, s_pa),
                "BB %": fmt_pct(s_bb, s_pa),
                "K %": fmt_pct(s_k, s_pa),
                "BABIP": fmt_rate(s_babip),
                "R": season_stats.get('runs', 0),
                "RBI": season_stats.get('rbi', 0),
                "SB": s_sb,
                "CS": s_cs,
                "SB %": fmt_pct(s_sb, s_sb + s_cs)
            },
            {
                "Split": "Recent",
                "G": recent_stats.get('gamesCounted', 0),
                "PA": r_pa,
                "AVG": fmt_rate(recent_stats.get('avg', 0)),
                "OBP": fmt_rate(recent_stats.get('obp', 0)),
                "SLG": fmt_rate(recent_stats.get('slg', 0)),
                "OPS": fmt_rate(r_ops),
                "H": r_h,
                "2B": r_2b,
                "3B": r_3b,
                "HR": r_hr,
                "BB": r_bb,
                "K": r_k,
                "HR %": fmt_pct(r_hr, r_pa),
                "XBH %": fmt_pct(r_2b + r_3b + r_hr, r_pa),
                "BB %": fmt_pct(r_bb, r_pa),
                "K %": fmt_pct(r_k, r_pa),
                "BABIP": fmt_rate(r_babip),
                "R": recent_stats.get('runs', 0),
                "RBI": recent_stats.get('rbi', 0),
                "SB": r_sb,
                "CS": r_cs,
                "SB %": fmt_pct(r_sb, r_sb + r_cs)
            }
        ])
        
        if cols[5].button("Stats", key=f"btn_bat_{pid}_{title}"):
            show_stats_dialog(f"#{info['jersey']} {info['name']}", df)

def render_pitchers(title, player_ids, team_data):
    st.subheader(title)

    pitcher_col_ratios = [1.0, 2.0, 1.0, 1.0, 1.0, 1.0]    
#    pitcher_col_ratios = [1.2, 2.2, 1.0, 1.0, 0.8, 1.0]
    
    cols = st.columns(pitcher_col_ratios, vertical_alignment="center")
    cols[0].write("**Pos (Thr.)**")
    cols[1].write("**Name**")
    cols[2].write("**sERA**")
    cols[3].write("**rERA**")
    cols[4].write("**Trend**")
    cols[5].write("**Detail**")
    st.divider()

    for pid in player_ids:
        info = get_player_info(team_data, pid)
        if not info: continue
        
        season_stats = fetch_player_season_stats(pid, "pitching")
        
        display_pos = info['def_pos']
        is_starter = True
        if display_pos == 'P':
            games_played = season_stats.get('gamesPlayed', 0)
            games_started = season_stats.get('gamesStarted', 0)
            if games_played > 0:
                if (games_started / games_played) > 0.5:
                    display_pos = 'SP'
                    is_starter = True
                else:
                    display_pos = 'RP'
                    is_starter = False
        else:
            is_starter = (display_pos == 'SP')
            
        limit_type = sp_limit_type if is_starter else rp_limit_type
        limit_val = sp_val if is_starter else rp_val
        
        game_logs = fetch_player_game_logs(pid, "pitching")
        recent_stats = calculate_trailing_pitcher_stats(game_logs, limit_type, limit_val, selected_date)
                    
        s_era = float(season_stats.get('era', 0.00))
        r_era = float(recent_stats.get('era', 0.00))
        
        cols = st.columns(pitcher_col_ratios, vertical_alignment="center")
        cols[0].write(f"{display_pos} ({info['pitch_hand']})")
#        cols[1].write(f"#{info['jersey']} {info['name']}")
        cols[1].markdown(f'<div class="mobile-name-col">#{info["jersey"]} {info["name"]}</div>', unsafe_allow_html=True)
        cols[2].write(f"{s_era:.2f}")
        cols[3].write(f"{r_era:.2f}")
        cols[4].write(calculate_pitcher_trend(s_era, r_era))
        
        s_outs = ip_to_outs(season_stats.get('inningsPitched', '0.0'))
        s_ip_calc = s_outs / 3.0
        s_h = season_stats.get('hits', 0)
        s_2b = season_stats.get('doubles', 0)
        s_3b = season_stats.get('triples', 0)
        s_hr = season_stats.get('homeRuns', 0)
        s_bb = season_stats.get('baseOnBalls', 0)
        s_hbp = season_stats.get('hitByPitch', 0) or season_stats.get('hitBatsmen', 0)
        s_k = season_stats.get('strikeOuts', 0)
        s_bf = season_stats.get('battersFaced', 0)
        s_ab = season_stats.get('atBats', 0)
        s_sf = season_stats.get('sacFlies', 0) or season_stats.get('sacrificeFlies', 0)
        
        s_fip = (((13 * s_hr) + (3 * (s_bb + s_hbp)) - (2 * s_k)) / s_ip_calc + 3.083) if s_ip_calc > 0 else 0.00
        s_whip = (s_bb + s_h) / s_ip_calc if s_ip_calc > 0 else 0.00
        s_babip_den = s_ab - s_hr - s_k + s_sf
        s_babip = (s_h - s_hr) / s_babip_den if s_babip_den > 0 else 0.0
        
        r_outs = ip_to_outs(recent_stats.get('inningsPitched', '0.0'))
        r_ip_calc = r_outs / 3.0
        r_h = recent_stats.get('hits', 0)
        r_2b = recent_stats.get('doubles', 0)
        r_3b = recent_stats.get('triples', 0)
        r_hr = recent_stats.get('homeRuns', 0)
        r_bb = recent_stats.get('baseOnBalls', 0)
        r_hbp = recent_stats.get('hitByPitch', 0)
        r_k = recent_stats.get('strikeOuts', 0)
        r_bf = recent_stats.get('battersFaced', 0)
        r_ab = recent_stats.get('atBats', 0)
        r_sf = recent_stats.get('sacFlies', 0)
        
        r_fip = recent_stats.get('fip', 0.00)
        r_whip = (r_bb + r_h) / r_ip_calc if r_ip_calc > 0 else 0.00
        r_babip_den = r_ab - r_hr - r_k + r_sf
        r_babip = (r_h - r_hr) / r_babip_den if r_babip_den > 0 else 0.0
        
        df = pd.DataFrame([
            {
                "Split": "Season",
                "G": season_stats.get('gamesPlayed', 0),
                "IP": season_stats.get('inningsPitched', 0),
                "ERA": f"{s_era:.2f}",
                "FIP": f"{s_fip:.2f}",
                "BAA": fmt_rate(season_stats.get('avg', 0)),
                "OBP": fmt_rate(season_stats.get('obp', 0)),
                "SLG": fmt_rate(season_stats.get('slg', 0)),
                "OPS": fmt_rate(season_stats.get('ops', 0)),
                "BF": s_bf,
                "ER": season_stats.get('earnedRuns', 0),
                "R": season_stats.get('runs', 0),
                "H": s_h,
                "2B": s_2b,
                "3B": s_3b,
                "HR": s_hr,
                "BB": s_bb,
                "K": s_k,
                "HBP": s_hbp,
                "HR %": fmt_pct(s_hr, s_bf),
                "XBH %": fmt_pct(s_2b + s_3b + s_hr, s_bf),
                "BB %": fmt_pct(s_bb, s_bf),
                "K %": fmt_pct(s_k, s_bf),
                "WHIP": f"{s_whip:.2f}",
                "BABIP": fmt_rate(s_babip)
            },
            {
                "Split": "Recent",
                "G": recent_stats.get('gamesCounted', 0),
                "IP": recent_stats.get('inningsPitched', 0),
                "ERA": f"{r_era:.2f}",
                "FIP": f"{r_fip:.2f}",
                "BAA": fmt_rate(recent_stats.get('baa', 0)),
                "OBP": fmt_rate(recent_stats.get('obpa', 0)),
                "SLG": fmt_rate(recent_stats.get('slga', 0)),
                "OPS": fmt_rate(recent_stats.get('opsa', 0)),
                "BF": r_bf,
                "ER": recent_stats.get('earnedRuns', 0),
                "R": recent_stats.get('runs', 0),
                "H": r_h,
                "2B": r_2b,
                "3B": r_3b,
                "HR": r_hr,
                "BB": r_bb,
                "K": r_k,
                "HBP": r_hbp,
                "HR %": fmt_pct(r_hr, r_bf),
                "XBH %": fmt_pct(r_2b + r_3b + r_hr, r_bf),
                "BB %": fmt_pct(r_bb, r_bf),
                "K %": fmt_pct(r_k, r_bf),
                "WHIP": f"{r_whip:.2f}",
                "BABIP": fmt_rate(r_babip)
            }
        ])
        
        if cols[5].button("Stats", key=f"btn_pit_{pid}_{title}"):
            show_stats_dialog(f"#{info['jersey']} {info['name']}", df)

def get_batter_sops(pid):
    season_stats = fetch_player_season_stats(pid, "hitting")
    try:
        return float(season_stats.get('ops', 0.0))
    except:
        return 0.0

def get_bullpen_sort_key(pid, team_dict):
    # 1. Role: RP (0) comes before SP (1)
    season_stats = fetch_player_season_stats(pid, "pitching")
    display_pos = get_player_info(team_dict, pid).get('def_pos', 'P')
    
    is_starter = False
    if display_pos == 'P':
        gp = season_stats.get('gamesPlayed', 0)
        gs = season_stats.get('gamesStarted', 0)
        if gp > 0 and (gs / gp) > 0.5:
            is_starter = True
    elif display_pos == 'SP':
        is_starter = True
        
    role_val = 1 if is_starter else 0  # 0 for RP, 1 for SP
    
    # 2. Season ERA (default to a high number if missing so they sort last)
    try:
        era = float(season_stats.get('era', 999.0))
    except:
        era = 999.0
        
    return (role_val, era)

def render_team_tab(team_dict):

    
    st.caption("sOPS = Season OPS; rOPS = Recent OPS")
    
    batting_order = team_dict.get('battingOrder', [])
    bench = team_dict.get('bench', [])
    all_batters = team_dict.get('batters', [])
    
    batters_left_game = []
    for p in all_batters:
        if p not in batting_order and p not in bench:
            p_info = get_player_info(team_dict, p)
            if p_info and p_info['def_pos'] != 'P':
                batters_left_game.append(p)
                
    all_pitchers = team_dict.get('pitchers', [])
    bullpen = team_dict.get('bullpen', [])
    
    if len(all_pitchers) > 0:
        current_pitcher = [all_pitchers[-1]]
        pitchers_left_game = all_pitchers[:-1]
    else:
        current_pitcher = []
        pitchers_left_game = []
    
    render_batters("Current Lineup", batting_order, team_dict)
    
    if bench:
        # Sort bench batters by Season OPS (sOPS) descending (highest first)
        sorted_bench = sorted(bench, key=lambda pid: get_batter_sops(pid), reverse=True)
        render_batters("Bench", sorted_bench, team_dict)
        
    if batters_left_game:
        render_batters("Batters - Left Game", batters_left_game, team_dict)
    
#    st.caption("sOPS = Season OPS; rOPS = Recent OPS")
    st.write("")

    st.caption("sERA = Season ERA; rERA = Recent ERA")
        
    render_pitchers("Current Pitcher", current_pitcher, team_dict)
    
    if bullpen:
        # Sort bullpen: RP first (0), then SP (1), with lowest ERA first within each group
        sorted_bullpen = sorted(bullpen, key=lambda pid: get_bullpen_sort_key(pid, team_dict))
        render_pitchers("Bullpen", sorted_bullpen, team_dict)
        
    if pitchers_left_game:
        render_pitchers("Pitchers - Left Game", pitchers_left_game, team_dict)

#    st.caption("sERA = Season ERA; rERA = Recent ERA")

if selected_team == away_team:
    render_team_tab(boxscore['away'])
else:
    render_team_tab(boxscore['home'])
