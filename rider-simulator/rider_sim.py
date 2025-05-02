import json
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ────────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Simulator", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # Sidebar configuration
    st.sidebar.header("Batch Settings")
    n_exp = st.sidebar.number_input("Number of EXP Riders", min_value=0, max_value=100, value=25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", min_value=0, max_value=100, value=10, key="n_foc")

    st.sidebar.header("Timing Mode")
    mode = st.sidebar.radio("Timing type", ["Per-Zone", "Whole Lap"], index=0, key="timing_mode")

    if mode == "Per-Zone":
        st.sidebar.subheader("Zone Durations (minutes)")
        a_time = st.sidebar.number_input("Zone A time", 0.0, 60.0, 5.0, 0.1, key="per_a")
        b_time = st.sidebar.number_input("Zone B time", 0.0, 60.0, 5.0, 0.1, key="per_b")
        c_time = st.sidebar.number_input("Zone C time", 0.0, 60.0, 5.0, 0.1, key="per_c")
        lap_time = a_time + b_time + c_time
    else:
        st.sidebar.subheader("Lap Duration (minutes)")
        lap_time = st.sidebar.number_input("Whole lap time", 0.0, 180.0, 15.0, 0.1, key="lap_time")
        # For animation, split lap equally into 3 segments
        a_time = b_time = c_time = lap_time / 3.0

    # Run
    if st.sidebar.button("Start Simulation", key="run_sim"):
        # Compute stage durations
        exit_dur = 0.5  # fixed exit return to queue

        # Compute start times
        inst_start = 0.0
        inst_finish = inst_start + lap_time

        exp_start = inst_finish
        exp_finish = exp_start + lap_time if n_exp > 0 else exp_start

        foc_start = exp_finish
        foc_finish = foc_start + lap_time if n_foc > 0 else foc_start

        total_time = foc_finish + exit_dur

        # Build rider records
        riders = []
        # Instructor
        riders.append({"id":"INST", "start":inst_start, "lap":lap_time})
        # EXP batch
        for i in range(1, n_exp+1):
            riders.append({"id":f"EXP{i}", "start":exp_start, "lap":lap_time})
        # FOC batch
        for i in range(1, n_foc+1):
            riders.append({"id":f"FOC{i}", "start":foc_start, "lap":lap_time})

        # Summary
        st.subheader("Simulation Results")
        st.write(f"Total elapsed: **{total_time:.2f}** minutes")
        st.write(f"Instructor done at {inst_finish:.2f} min; EXP done at {exp_finish:.2f} min; FOC done at {foc_finish:.2f} min")

        # Prepare data for animation
        riders_json = json.dumps(riders)
        html = (
            "<div style='font:16px monospace;' id='timer'>Time: 0.00 min</div>"
            "<canvas id='track' width='800' height='300'></canvas>"
            "<script>\n"
            "const riders = " + riders_json + ";\n"
            "const totalTime = " + str(total_time) + ";\n"
            "const dt = 0.05; const exitDur=0.5;\n"
            "const ctx = document.getElementById('track').getContext('2d');\n"
            "const timerDiv = document.getElementById('timer');\n"
            // Define region boxes
            "const regions = [ {name:'Queue', x:20, w:60}, {name:'A', x:100, w:200}, {name:'B', x:320, w:200}, {name:'C', x:540, w:200}, {name:'Exit', x:760, w:40} ];\n"
            // y positions
            "const ypos = {INST:80, EXP:160, FOC:240};\n"
            "let t=0; function draw(){\n"
            "  ctx.clearRect(0,0,800,300); ctx.font='14px sans-serif';\n"
            "  regions.forEach(r=>{ ctx.strokeRect(r.x,40, r.w,200); ctx.fillText(r.name, r.x+5,30); });\n"
            "  timerDiv.innerText = 'Time: '+t.toFixed(2)+' min';\n"
            "  riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x, y=ypos[r.id.match(/[A-Z]+/)[0]];\n"
            // position calculation
            "    if(e<r.lap){ let f=e/r.lap; if(f<1/3) x=regions[1].x+f*3*regions[1].w; else if(f<2/3) x=regions[2].x+(f-1/3)*3*regions[2].w; else x=regions[3].x+(f-2/3)*3*regions[3].w; }\n"
            "    else if(e<r.lap+exitDur){ let f=(e-r.lap)/exitDur; x=regions[4].x + f*regions[4].w; }\n"
            "    else x=regions[0].x + regions[0].w/2;\n"
            "    ctx.beginPath(); ctx.fillStyle = r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue'; ctx.arc(x,y,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id, x-10, y+20); });\n"
            "  t+=dt; if(t<totalTime+1) requestAnimationFrame(draw); }\n"
            "draw();\n"
            "</script>"
        )
        components.html(html, height=320)

if __name__=='__main__': main()
