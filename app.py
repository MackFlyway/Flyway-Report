import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from folium.features import DivIcon
from geopy.geocoders import Nominatim
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="The Flyway Report", page_icon="🦆", layout="wide")

EBIRD_API_KEY = "csmhpchaskbq"
USER_AGENT = "flyway_report_v7_failsafe"

# SPECIES WHITELIST
HUNTABLE_SPECIES = {
    "Mallard", "Northern Pintail", "American Wigeon", "Gadwall", 
    "Green-winged Teal", "Cinnamon Teal", "Blue-winged Teal", 
    "Northern Shoveler", "Wood Duck", "Canvasback", "Redhead", 
    "Ring-necked Duck", "Greater Scaup", "Lesser Scaup", 
    "Canada Goose", "Snow Goose", "Greater White-fronted Goose", "Brant",
    "Cackling Goose", "Ross's Goose", "Tundra Swan"
}

# --- FAIL-SAFE COORDINATES (Instant Lookup) ---
# Add your favorite towns here to make them bulletproof
MANUAL_LOCATIONS = {
    "brawley": (32.978, -115.530),
    "niland": (33.237, -115.513),
    "calipatria": (33.125, -115.514),
    "imperial": (32.847, -115.569),
    "el centro": (32.792, -115.563),
    "los banos": (37.058, -120.849),
    "willows": (39.524, -122.193),
    "sacramento": (38.581, -121.494),
    "colusa": (39.214, -122.009),
    "yuba city": (39.140, -121.616),
    "tulelake": (41.956, -121.477),
    "klamath falls": (42.224, -121.781),
    "salt lake city": (40.760, -111.891),
    "boise": (43.615, -116.202),
    "reno": (39.529, -119.813),
    "yuma": (32.692, -114.627),
}

# --- THE MASTER HOTSPOT DATABASE ---
KNOWN_HOTSPOTS = [
    # === MONTANA ===
    {"name": "Lee Metcalf NWR (MT)", "lat": 46.567, "lon": -114.083},
    {"name": "Benton Lake NWR (MT)", "lat": 47.666, "lon": -111.316},
    {"name": "Freezeout Lake (MT)", "lat": 47.650, "lon": -112.033},

    # === IDAHO ===
    {"name": "Deer Flat NWR (ID)", "lat": 43.565, "lon": -116.751},
    {"name": "Camas NWR (ID)", "lat": 43.955, "lon": -112.231},
    {"name": "Minidoka NWR (ID)", "lat": 42.665, "lon": -113.493},
    {"name": "Market Lake WMA (ID)", "lat": 43.783, "lon": -112.150},

    # === UTAH ===
    {"name": "Bear River Migratory Bird Refuge (UT)", "lat": 41.458, "lon": -112.272},
    {"name": "Farmington Bay WMA (UT)", "lat": 40.976, "lon": -111.956},
    {"name": "Ogden Bay WMA (UT)", "lat": 41.200, "lon": -112.116},
    {"name": "Clear Lake WMA (UT)", "lat": 39.100, "lon": -112.600},

    # === NEVADA ===
    {"name": "Stillwater NWR (NV)", "lat": 39.527, "lon": -118.528},
    {"name": "Ruby Lake NWR (NV)", "lat": 40.200, "lon": -115.483},
    {"name": "Pahranagat NWR (NV)", "lat": 37.283, "lon": -115.116},
    {"name": "Ash Meadows NWR (NV)", "lat": 36.416, "lon": -116.283},

    # === ARIZONA ===
    {"name": "Havasu NWR (AZ)", "lat": 34.733, "lon": -114.533},
    {"name": "Cibola NWR (AZ)", "lat": 33.316, "lon": -114.683},
    {"name": "Imperial NWR (AZ)", "lat": 32.966, "lon": -114.466},
    {"name": "Mittry Lake (AZ)", "lat": 32.816, "lon": -114.466},

    # === WASHINGTON/OREGON ===
    {"name": "Skagit Wildlife Area (WA)", "lat": 48.375, "lon": -122.463},
    {"name": "Ridgefield NWR (WA)", "lat": 45.827, "lon": -122.753},
    {"name": "Sauvie Island (OR)", "lat": 45.656, "lon": -122.812},
    {"name": "Summer Lake (OR)", "lat": 42.955, "lon": -120.768},
    {"name": "Lower Klamath NWR (Border)", "lat": 41.967, "lon": -121.667},

    # === CALIFORNIA ===
    {"name": "Sacramento NWR (CA)", "lat": 39.407, "lon": -122.187},
    {"name": "Gray Lodge WA (CA)", "lat": 39.324, "lon": -121.821},
    {"name": "San Luis NWR (CA)", "lat": 37.176, "lon": -120.825},
    {"name": "Kern NWR (CA)", "lat": 35.733, "lon": -119.600},
    {"name": "San Jacinto WA (SoCal)", "lat": 33.883, "lon": -117.117},
    {"name": "Wister Unit (Salton Sea)", "lat": 33.266, "lon": -115.583},
]

# --- HELPER FUNCTIONS ---

@st.cache_data
def get_coordinates(place_name):
    """
    1. Checks MANUAL_LOCATIONS list first (Instant/Robust).
    2. Falls back to Geocoder if not found.
    """
    # Clean input: "Brawley, CA" -> "brawley"
    clean_name = place_name.lower().split(',')[0].strip()
    
    # 1. Manual Check
    if clean_name in MANUAL_LOCATIONS:
        return MANUAL_LOCATIONS[clean_name]
        
    # 2. Internet Check
    geolocator = Nominatim(user_agent=USER_AGENT)
    try:
        location = geolocator.geocode(place_name)
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

def get_bird_data(lat, lon):
    url = "https://api.ebird.org/v2/data/obs/geo/recent"
    headers = {"X-eBirdApiToken": EBIRD_API_KEY}
    params = {"lat": lat, "lng": lon, "dist": 30, "back": 10, "cat": "species"} 
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        return response.json() if response.status_code == 200 else []
    except: return []

def get_weather_data(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "current_weather": True}
        r = requests.get(url, params=params, timeout=3).json()
        return r.get('current_weather', {})
    except: return None

def get_weather_emoji(wmo_code):
    if wmo_code is None: return "❓"
    if wmo_code == 0: return "☀️" 
    if wmo_code in [1, 2, 3]: return "⛅"
    if wmo_code in [45, 48]: return "🌫️"
    if 51 <= wmo_code <= 67: return "🌧️"
    if 71 <= wmo_code <= 77: return "❄️"
    if 80 <= wmo_code <= 82: return "🌦️"
    if 95 <= wmo_code <= 99: return "⛈️"
    return "⛅"

def process_date(obs_date_str):
    try:
        obs_date = datetime.strptime(obs_date_str, '%Y-%m-%d %H:%M')
    except:
        try: obs_date = datetime.strptime(obs_date_str, '%Y-%m-%d')
        except: obs_date = datetime.now()
    
    days_old = (datetime.now() - obs_date).days
    
    if days_old == 0: date_text = "Today"
    elif days_old == 1: date_text = "Yesterday"
    else: date_text = f"{days_old} days ago"

    if days_old <= 2: return 'green', date_text
    elif days_old <= 7: return 'orange', date_text
    else: return 'red', date_text

# --- UI LAYOUT ---
st.title("🦆 The Flyway Report")
st.markdown("Real-time Intelligence for the Modern Waterfowler.")

with st.sidebar:
    st.header("Settings")
    # UPDATED: Help text
    location_input = st.text_input("Enter City (e.g., Brawley, Colusa)", value="Brawley")
    run_button = st.button("Generate Report 🚀", type="primary")
    st.divider()
    st.markdown("### Legend")
    st.markdown("🟢 **Green:** Fresh (<48 hrs)")
    st.markdown("🔴 **Red:** Stale (>1 week)")
    st.markdown("⛈️ **Weather:** Real-time icons.")

if run_button:
    with st.spinner("Compiling The Flyway Report..."):
        start_lat, start_lon = get_coordinates(location_input)
        
        # FINAL FALLBACK: If everything fails, land on Salton Sea
        if not start_lat:
            st.warning(f"Could not pinpoint '{location_input}'. Centering on Salton Sea.")
            start_lat, start_lon = 33.3, -115.6

        m = folium.Map(location=[start_lat, start_lon], zoom_start=6, tiles="Cartodb Positron")
        folium.Marker([start_lat, start_lon], icon=folium.Icon(color='blue', icon='home'), tooltip="Center").add_to(m)

        total_birds = 0
        
        for hotspot in KNOWN_HOTSPOTS:
            birds = get_bird_data(hotspot['lat'], hotspot['lon'])
            weather = get_weather_data(hotspot['lat'], hotspot['lon'])
            
            w_code = weather.get('weathercode') if weather else None
            w_emoji = get_weather_emoji(w_code)
            w_temp = weather.get('temperature', 'N/A') if weather else 'N/A'
            
            folium.map.Marker(
                [hotspot['lat'], hotspot['lon']],
                icon=DivIcon(
                    icon_size=(50,50),
                    icon_anchor=(25,25),
                    html=f'<div style="font-size: 40px; opacity: 0.7;">{w_emoji}</div>'
                ),
                tooltip=f"{hotspot['name']}: {w_temp}°F"
            ).add_to(m)

            for bird in birds:
                name = bird.get('comName')
                if name in HUNTABLE_SPECIES:
                    count = bird.get('howMany', 1)
                    date_str = bird.get('obsDt')
                    lat = bird.get('lat')
                    lng = bird.get('lng')
                    
                    color, time_ago = process_date(date_str)
                    
                    popup_html = f"""
                    <div style="font-family:sans-serif; min-width:140px;">
                        <b>{name}</b><br>
                        Quantity: {count}<br>
                        Seen: {date_str}<br>
                        <span style="color:{color}; font-weight:bold;">({time_ago})</span>
                    </div>
                    """
                    
                    # Ring
                    folium.CircleMarker(
                        location=[lat, lng],
                        radius=4 + (count * 0.01),
                        color=color,
                        fill=True, fill_opacity=0.5,
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=f"{name} ({count}) - {time_ago}"
                    ).add_to(m)
                    
                    # Duck Icon
                    folium.map.Marker(
                        [lat, lng],
                        icon=DivIcon(
                            icon_size=(20,20),
                            icon_anchor=(10,10),
                            html=f'<div style="font-size: 16px;">🦆</div>'
                        ),
                        popup=folium.Popup(popup_html, max_width=200),
                        tooltip=f"{name} ({count}) - {time_ago}"
                    ).add_to(m)
                    
                    total_birds += 1
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Sectors Scanned", len(KNOWN_HOTSPOTS))
        c2.metric("Birds Tracked", total_birds)
        c3.metric("System Status", "Online")
        
        st_folium(m, width=1200, height=700, returned_objects=[])
