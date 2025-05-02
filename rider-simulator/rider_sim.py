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
    n_exp = st.sidebar.number_input(
        "Number of EXP Riders", min_value=0, max_value=100, value=25, key="n_exp"
    )
    n_foc = st.sidebar.number_input(
        "Number of FOC Riders", min_value=0, max_value=100, value=10, key="n_foc"
    )

    st.sidebar.header("Timing Mode")
    mode = st.sidebar.radio(
        "Timing type", ["Per-Zone", "Whole Lap"], index=0, key="timing_mode"
    )

    if mode == "Per-Zone":
        st.sidebar.subheader("Zone Durations (minutes)")
        a_time = st.sidebar.number_input(
            "Zone A time", 0.0, 60.0, 5.0, 0.1, key="per_a"
        )
        b_time = st.sidebar.number_input(
            "Zone B time", 0.0, 60.0, 5.0, 0.1, key="per_b"
        )
        c_time = st.sidebar.number_input(
            "Zone C time", 0.0, 60.0, 5.0, 0.1, key="per_c"
        )
        lap_time = a_time + b_time + c_time
    else:
        st.sidebar.subheader("Lap Duration (minutes)")
        lap_time = st.sidebar.number_input(
            "Whole lap time", 0.0, 180.0, 15.0, 0.1, key="lap_time"
        )
        # For animation, split lap equally into 3 segments
        a_time = b_time = c_time = lap_time / 3.0

    # Run simulation
    if st.sidebar.button("Start Simulation", key="run_sim"):
        exit_dur = 0.5  # fixed exit return to queue

        # Instructor timings
        inst_start = 0.0
        inst_finish = inst_start + lap_time

        # Build riders sequentially
        riders = []
        # Instructor
        riders.append({"id": "INST", "start": inst_start, "a": a_time, "b": b_time, "c": c_time})

        # EXP sequential: each starts when previous exits + exit_dur
        current = inst_finish + exit_dur
        for i in range(1, n_exp + 1):
            riders.append({"id": f"EXP{i}", "start": current, "a": a_time, "b": b_time, "c": c_time})
            current += lap_time + exit_dur
        exp_finish = current - exit_dur if n_exp > 0 else inst_finish

        # FOC sequential
        current = exp_finish + exit_dur
        for i in range(1, n_foc + 1):
            riders.append({"id": f"FOC{i}", "start": current, "a": a_time, "b": b_time, "c": c_time})
            current += lap_time + exit_dur
        foc_finish = current - exit_dur if n_foc > 0 else exp_finish

        total_time = foc_finish

        # Display summary
        st.subheader("Simulation Results")
        st.write(f"Total elapsed: **{total_time:.2f}** minutes")
        st.write(f"Instructor done at {inst_finish:.2f} min")
        if n_exp > 0:
            st.write(f"EXP batch finished at: {exp_finish:.2f} min")
        if n_foc > 0:
            st.write(f"FOC batch finished at: {foc_finish:.2f} min")

        # Prepare for animation
        riders_json = json.dumps(riders)
        html = (
            "<div style='font:16px monospace;' id='timer'>Time: 0.00 min</div>"
            "<canvas id='track' width='900' height='320'></canvas>"
            "<script>\n"
            "const riders = " + riders_json + ";\n"
            "const totalTime = " + str(total_time) + ";\n"
            "const dt = 0.05; const exitDur=0.5;\n"
            "const ctx = document.getElementById('track').getContext('2d');\n"
            "const timerDiv = document.getElementById('timer');\n"
            # Regions definition
            "const regions = ["
            "{name:'Queue', x:20, w:80},"
            "{name:'A', x:120, w:200},"
            "{name:'B', x:340, w:200},"
            "{name:'C', x:560, w:200},"
            "{name:'Exit', x:780, w:80}"  # riders return to queue area x:20
            "];\n"
            "const ypos = {INST:80, EXP:160, FOC:240};\n"
            "let t=0; function draw(){\n"
            "  ctx.clearRect(0,0,900,320); ctx.font='14px sans-serif';\n"
            "  regions.forEach(r=>{ ctx.strokeRect(r.x,40,r.w,220); ctx.fillText(r.name,r.x+5,30); });\n"
            "  timerDiv.innerText = 'Time: ' + t.toFixed(2) + ' min';\n"
            "  riders.forEach(r=>{ if(t<r.start) return; let e = t - r.start; let x,y = ypos[r.id.match(/[A-Z]+/)[0]];\n"
            # Movement logic
            "    if(e < r.a){ x = regions[1].x + (e/r.a)*regions[1].w; }\n"
            "    else if(e < r.a + r.b){ e -= r.a; x = regions[2].x + (e/r.b)*regions[2].w; }\n"
            "    else if(e < r.a + r.b + r.c){ e -= (r.a + r.b); x = regions[3].x + (e/r.c)*regions[3].w; }\n"
            "    else if(e < r.a + r.b + r.c + exitDur){ e -= (r.a + r.b + r.c); x = regions[4].x + (e/exitDur)*regions[4].w; }\n"
            "    else{ x = regions[0].x + regions[0].w/2; }\n"
            "    ctx.beginPath(); ctx.fillStyle = r.id.startsWith('INST') ? 'red' : r.id.startsWith('EXP') ? 'green' : 'blue';\n"
            "    ctx.arc(x,y,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id, x-10, y+20); });\n"
            "  t += dt; if(t < totalTime + 1) requestAnimationFrame(draw); }\n"
            "draw();\n"
            "</script>"
        )
        components.html(html, height=360)

if __name__ == '__main__':
    main()
