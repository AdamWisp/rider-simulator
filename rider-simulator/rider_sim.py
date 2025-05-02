import json
import time
import streamlit as st
import streamlit.components.v1 as components

# ────────────────────────────── Streamlit UI ────────────────────────────── #
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
        a_time = st.sidebar.number_input("Zone A time", 0.0, 60.0, 5.0, 0.1, key="per_a")
        b_time = st.sidebar.number_input("Zone B time", 0.0, 60.0, 5.0, 0.1, key="per_b")
        c_time = st.sidebar.number_input("Zone C time", 0.0, 60.0, 5.0, 0.1, key="per_c")
        cap_zone = st.sidebar.number_input("Riders per zone", 1, 2, 1, key="cap_zone")
        lap_time = a_time + b_time + c_time
    else:
        st.sidebar.subheader("Lap Duration (minutes)")
        lap = st.sidebar.number_input("Whole lap time", 0.0, 180.0, 15.0, 0.1, key="lap_time")
        a_time = b_time = c_time = lap / 3.0
        cap_zone = 1
        lap_time = lap

    # Start simulation
    if st.sidebar.button("Start Simulation", key="run_sim"):
        exit_dur = 0.5  # fixed exit return to queue

        # Pipeline allowing zone capacity
        def pipeline(start_time, count, a_d, b_d, c_d, cap, prefix):
            # initialize free times lists
            zoneA_free = [start_time] * cap
            zoneB_free = [start_time] * cap
            zoneC_free = [start_time] * cap
            riders_list = []
            for i in range(1, count + 1):
                rid = f"{prefix}{i if prefix!='INST' else ''}"
                # Zone A
                a_idx = min(range(cap), key=lambda idx: zoneA_free[idx])
                a_start = zoneA_free[a_idx]
                zoneA_free[a_idx] = a_start + a_d
                # Zone B
                b_ready = a_start + a_d
                b_idx = min(range(cap), key=lambda idx: max(zoneB_free[idx], b_ready))
                b_start = max(zoneB_free[b_idx], b_ready)
                zoneB_free[b_idx] = b_start + b_d
                # Zone C
                c_ready = b_start + b_d
                c_idx = min(range(cap), key=lambda idx: max(zoneC_free[idx], c_ready))
                c_start = max(zoneC_free[c_idx], c_ready)
                zoneC_free[c_idx] = c_start + c_d
                # Exit
                exit_start = c_start + c_d
                finish = exit_start + exit_dur
                riders_list.append({
                    "id": rid,
                    "start": a_start,
                    "a": a_d,
                    "b": b_d,
                    "c": c_d,
                    "exit": exit_start,
                    "finish": finish
                })
            return riders_list

        # Instructor
        inst = pipeline(0.0, 1, a_time, b_time, c_time, cap_zone, 'INST')[0]
        exp_riders = pipeline(inst['finish'] + exit_dur, n_exp, a_time, b_time, c_time, cap_zone, 'EXP')
        exp_finish = exp_riders[-1]['finish'] if exp_riders else inst['finish']
        foc_riders = pipeline(exp_finish + exit_dur, n_foc, a_time, b_time, c_time, cap_zone, 'FOC')
        foc_finish = foc_riders[-1]['finish'] if foc_riders else exp_finish
        total_time = foc_finish

        # Summary
        st.subheader("Simulation Results")
        st.write(f"Total elapsed time: **{total_time:.2f}** minutes")
        st.write(f"Instructor finish: {inst['finish']:.2f} min")
        if exp_riders:
            st.write(f"Last EXP finished: {exp_finish:.2f} min")
        if foc_riders:
            st.write(f"Last FOC finished: {foc_finish:.2f} min")

        # Combine riders
        all_riders = [inst] + exp_riders + foc_riders
        riders_json = json.dumps(all_riders)

        # Animation HTML
        html = (
            "<div style='font:16px monospace;margin-bottom:5px;' id='timer'>Time: 0.00 min</div>"
            "<canvas id='track' width='900' height='360'></canvas>"
            "<script>\n"
            "const riders = " + riders_json + ";\n"
            "const totalTime = " + str(total_time) + ";\n"
            "const dt = 0.05; const exitDur = 0.5;\n"
            "const ctx = document.getElementById('track').getContext('2d');\n"
            "const timerDiv = document.getElementById('timer');\n"
            "const regions = ["
            "{name:'Queue', x:20, w:80},"
            "{name:'A', x:120, w:200},"
            "{name:'B', x:340, w:200},"
            "{name:'C', x:560, w:200},"
            "{name:'Exit', x:780, w:80}];\n"
            "const ypos = {INST:80, EXP:160, FOC:240};\n"
            "let t = 0; function draw(){\n"
            "  ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif';\n"
            "  regions.forEach(r=>{ ctx.strokeRect(r.x,40,r.w,260); ctx.fillText(r.name, r.x+5,30); });\n"
            "  timerDiv.innerText = 'Time: '+t.toFixed(2)+' min';\n"
            "  riders.forEach(r=>{ if(t < r.start) return; let e = t - r.start; let x, y = ypos[r.id.replace(/[0-9]/g,'')];\n"
            "    if(e < r.a){ x = regions[1].x + (e/r.a)*regions[1].w; }\n"
            "    else if(e < r.a + r.b){ e -= r.a; x = regions[2].x + (e/r.b)*regions[2].w; }\n"
            "    else if(e < r.a + r.b + r.c){ e -= (r.a + r.b); x = regions[3].x + (e/r.c)*regions[3].w; }\n"
            "    else if(e < r.a + r.b + r.c + exitDur){ e -= (r.a + r.b + r.c); x = regions[4].x + (e/exitDur)*regions[4].w; }\n"
            "    else{ x = regions[0].x + regions[0].w/2; }\n"
            "    ctx.beginPath(); ctx.fillStyle = r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue'; ctx.arc(x,y,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id, x-10,y+20); });\n"
            "  t += dt; if(t < totalTime + exitDur) requestAnimationFrame(draw); }\n"
            "draw();\n"
            "</script>"
        )
        components.html(html, height=400)

if __name__ == '__main__':
    main()
