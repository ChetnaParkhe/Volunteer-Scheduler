import streamlit as st
import pandas as pd
import datetime
import math

# --- CONFIGURATION ---
st.set_page_config(page_title="Volunteer Scheduler", layout="wide")
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
    table {font-size: 12px !important;}
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Volunteer Scheduler")
# st.info("Logic: Volunteers are sorted numerically for every shift. V-1, V-2, V-3, V-4 go to Counter 1.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Settings")
    selected_date = st.date_input("Roster Date", datetime.date.today())
    
    # Rotation Logic: Shift the starting group every day
    day_of_year = selected_date.timetuple().tm_yday
    rotation_index = day_of_year % 4
    
    st.caption(f"Rotation Cycle: {rotation_index + 1}/4 (Groups rotate daily to prevent burnout)")
    
    total_volunteers = st.number_input(
        "Total Volunteers", 
        value=250, 
        min_value=240, 
        step=1
    )

# --- CORE LOGIC ---
def generate_schedule(total_ppl, rot_idx):
    # 1. Create the Master List (V-1 to V-250)
    # We store them as dicts so we can sort by integer ID easily
    master_list = [{"id_str": f"V-{i}", "id_num": i} for i in range(1, total_ppl + 1)]
    
    # 2. Divide into 4 Groups (Cohorts)
    chunk = math.ceil(total_ppl / 4)
    groups = [
        master_list[0:chunk],           # Group A
        master_list[chunk:chunk*2],     # Group B
        master_list[chunk*2:chunk*3],   # Group C
        master_list[chunk*3:]           # Group D
    ]
    
    # 3. Rotate the Groups based on the date
    # (So Group A isn't always the morning shift)
    rotated_groups = groups[rot_idx:] + groups[:rot_idx]
    
    # Map them to abstract IDs for the schedule
    # '1' = Morning Start, '2' = Morning Support, '3' = Afternoon Start...
    cohort_map = {
        '1': rotated_groups[0],
        '2': rotated_groups[1],
        '3': rotated_groups[2],
        '4': rotated_groups[3]
    }
    
    return cohort_map

# --- SCHEDULE DEFINITION ---
cohort_data = generate_schedule(total_volunteers, rotation_index)

# Which groups work at what time?
# Peak = 4 people needed. Off-Peak = 2 people needed.
schedule_pattern = [
    # Time, [Active Groups], People Per Counter needed
    ("08:00 - 10:00 (Peak)", ['1', '2'], 4), 
    ("10:00 - 12:00 (Peak)", ['3', '4'], 4),
    ("12:00 - 14:00 (Peak)", ['1', '2'], 4),
    ("14:00 - 16:00 (Peak)", ['3', '4'], 4),
    ("16:00 - 18:00 (Off)",  ['1'],      2),
    ("18:00 - 20:00 (Off)",  ['2'],      2),
    ("20:00 - 22:00 (Off)",  ['3'],      2),
    ("22:00 - 00:00 (Off)",  ['4'],      2),
    ("00:00 - 02:00 (Off)",  ['1'],      2),
    ("02:00 - 04:00 (Off)",  ['2'],      2),
    ("04:00 - 06:00 (Off)",  ['3'],      2),
    ("06:00 - 08:00 (Off)",  ['4'],      2),
]

# --- BUILD THE TABLE ---
table_rows = []
reserves_log = []
counters = 30

# We process by Time Slot first this time, to calculate the pools correctly
# But for the display, we need Rows = Counters. 
# So we will pre-calculate the assignments.

# Dictionary to hold data: assignments[counter_index][time_slot] = "V-1, V-2..."
assignments = {i: {} for i in range(counters)}

for time_slot, active_group_keys, req_per_counter in schedule_pattern:
    
    # 1. MERGE: Get everyone working in this shift
    pool = []
    for key in active_group_keys:
        pool.extend(cohort_data[key])
        
    # 2. SORT: Ensure they are strictly 1, 2, 3...
    pool.sort(key=lambda x: x['id_num'])
    
    # 3. DISTRIBUTE: Assign to counters
    # We need total: 30 counters * req (4 or 2)
    current_idx = 0
    
    for i in range(counters):
        # Slice the next batch of people
        assigned_ppl = pool[current_idx : current_idx + req_per_counter]
        
        # Format names
        names_str = ", ".join([p['id_str'] for p in assigned_ppl])
        
        if not assigned_ppl:
            names_str = "⚠️ EMPTY"
        
        assignments[i][time_slot] = names_str
        
        # Move index forward
        current_idx += req_per_counter

    # 4. CATCH RESERVES: Anyone left in the pool?
    leftovers = pool[current_idx:]
    if leftovers:
        reserves_names = ", ".join([p['id_str'] for p in leftovers])
        reserves_log.append({"Time": time_slot, "Reserves": reserves_names})

# Convert assignments dict to List of Rows for DataFrame
final_table_data = []
for i in range(counters):
    row = {"Counter": f"Counter {i+1}"}
    # Add all time slots
    row.update(assignments[i])
    final_table_data.append(row)

# --- DISPLAY MAIN TABLE ---
df = pd.DataFrame(final_table_data)
st.write(f"### 📅 Master Schedule for {selected_date}")
st.dataframe(df, use_container_width=True)

# --- DISPLAY RESERVES ---
if reserves_log:
    st.write("### ➕ Floating Reserves (Extras)")
    st.info("These volunteers are ON DUTY but not assigned to a specific counter. Use them for breaks.")
    st.table(pd.DataFrame(reserves_log))

# --- DOWNLOAD ---
csv = df.to_csv(index=False).encode('utf-8')
st.download_button("Download CSV", csv, "sequential_roster.csv", "text/csv")

# --- 🔍 SEARCH FUNCTION ---
st.markdown("---")
st.header("🔍 Find Volunteer")
c1, c2 = st.columns([1, 3])
with c1:
    search_q = st.text_input("Volunteer ID (e.g. 100)")
with c2:
    if search_q:
        # Normalize input
        q_num = ''.join(filter(str.isdigit, search_q))
        if q_num:
            target = f"V-{int(q_num)}"
            st.subheader(f"Schedule for {target}")
            
            found = []
            # Search Main Table
            for idx, row in df.iterrows():
                for col in df.columns:
                    if col == "Counter": continue
                    if target in str(row[col]).split(", "):
                        found.append({"Time": col, "Location": row['Counter'], "Role": "Counter Duty"})
            
            # Search Reserves
            for item in reserves_log:
                if target in item['Reserves'].split(", "):
                    found.append({"Time": item['Time'], "Location": "Reserve Area", "Role": "Standby"})
            
            if found:
                st.table(pd.DataFrame(found))
            else:
                st.warning("No active duty found (Rest Day).")