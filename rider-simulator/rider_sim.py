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

    st.sidebar.header("Zone Capacity")
    cap_zone = st.sidebar.number_input(
        "Riders per zone", min_value=1, max_value=2, value=1, key="cap_zone"
    )

    st.sidebar.header("Timing Mode")
    mode = st.sidebar.radio(
        "Timing type", ["Per-Zone", "Whole Lap"], index=0, key="timing_mode"
    )

    # Per-zone or whole-lap durations
    if mode == "Per-Zone":
        st.sidebar.subheader("Instructor Zone Times (min)")
        inst_a = st.sidebar.number_input("INST Zone A", 0.0, 60.0, 5.0, 0.1, key="inst_a")
        inst_b = st.sidebar.number_input("INST Zone B", 0.0, 60.0, 5.0, 0.1, key="inst_b")
        inst_c = st.sidebar.number_input("INST Zone C", 0.0, 60.0, 5.0, 0.1, key="inst_c")
        st.sidebar.subheader("EXP Zone Times (min)")
        exp_a = st.sidebar.number_input("EXP Zone A", 0.0, 60.0, 4.0, 0.1, key="exp_a")
        exp_b = st.sidebar.number_input("EXP Zone B", 0.0, 60.0, 4.0, 0.1, key="exp_b")
        exp_c = st.sidebar.number_input("EXP Zone C", 0.0, 60.0, 4.0, 0.1, key="exp_c")
        st.sidebar.subheader("FOC Zone Times (min)")
        foc_a = st.sidebar.number_input("FOC Zone A", 0.0, 60.0, 3.0, 0.1, key="foc_a")
        foc_b = st.sidebar.number_input("FOC Zone B", 0.0, 60.0, 3.0, 0.1, key="foc_b")
        foc_c = st.sidebar.number_input("FOC Zone C", 0.0, 60.0, 3.0, 0.1, key="foc_c")
        lap_div = False
    else:
        st.sidebar.subheader("Whole Lap Times (min)")
        inst_lap = st.sidebar.number_input("INST Whole Lap", 0.0, 180.0, 15.0, 0.1, key="inst_lap")
        exp_lap = st.sidebar.number_input("EXP Whole Lap", 0.0, 180.0, 12.0, 0.1, key="exp_lap")
        foc_lap = st.sidebar.number_input("FOC Whole Lap", 0.0, 180.0, 10.0, 0.1, key="foc_lap")
        # split lap equally into zones
        inst_a = inst_b = inst_c = inst_lap / 3.0
        exp_a = exp_b = exp_c = exp_lap / 3.0
        foc_a = foc_b = foc_c = foc_lap / 3.0
        lap_div = True

    # Test times (only one rider at a time)
    st.sidebar.subheader("Test Times (min)")
    inst_test = st.sidebar.number_input("INST Test", 0.0, 180.0, 5.0, 0.1, key="inst_test")
    exp_test = st.sidebar.number_input("EXP Test", 0.0, 180.0, 4.0, 0.1, key="exp_test")
    foc_test = st.sidebar.number_input("FOC Test", 0.0, 180.0, 3.0, 0.1, key="foc_test")

    # Start simulation
    if st.sidebar.button("Start Simulation", key="run_sim"):
        exit_dur = 0.5  # exit and return to queue

        # Pipeline with zone capacity and single-test resource
        def pipeline(start_time, count, a_d, b_d, c_d, test_d, cap, prefix):
            zoneA_free = [start_time] * cap
            zoneB_free = [start_time] * cap
            zoneC_free = [start_time] * cap
            test_free = start_time
            riders_list = []
            for i in range(1, count + 1):
                rid = f"{prefix}{i if prefix != 'INST' else ''}"
                # Zone A
                idx_a = min(range(cap), key=lambda idx: zoneA_free[idx])
                t_a = zoneA_free[idx_a]
                zoneA_free[idx_a] = t_a + a_d
                # Zone B
                ready_b = t_a + a_d
                idx_b = min(range(cap), key=lambda idx: max(zoneB_free[idx], ready_b))
                t_b = max(zoneB_free[idx_b], ready_b)
                zoneB_free[idx_b] = t_b + b_d
                # Zone C
                ready_c = t_b + b_d
                idx_c = min(range(cap), key=lambda idx: max(zoneC_free[idx], ready_c))
                t_c = max(zoneC_free[idx_c], ready_c)
                zoneC_free[idx_c] = t_c + c_d
                # Test (capacity 1)
                ready_t = t_c + c_d
                t_test = max(test_free, ready_t)
                test_free = t_test + test_d
                # Exit
                t_exit = test_free
                t_finish = t_exit + exit_dur
                riders_list.append({
                    "id": rid,
                    "start": t_a,
                    "a": a_d,
                    "b": b_d,
                    "c": c_d,
                    "test": test_d,
                    "exit": t_exit,
                    "finish": t_finish
                })
            return riders_list

        # Generate schedules
        inst = pipeline(0.0, 1, inst_a, inst_b, inst_c, inst_test, cap_zone, 'INST')[0]
        exp_start = inst['finish']
        exp_riders = pipeline(exp_start, n_exp, exp_a, exp_b, exp_c, exp_test, cap_zone, 'EXP')
        last_exp = exp_riders[-1]['finish'] if exp_riders else inst['finish']
        foc_start = last_exp
        foc_riders = pipeline(foc_start, n_foc, foc_a, foc_b, foc_c, foc_test, cap_zone, 'FOC')
        last_foc = foc_riders[-1]['finish'] if foc_riders else last_exp
        total_time = last_foc

        # Display summary
        st.subheader("Simulation Results")
        st.write(f"Total elapsed time: **{total_time:.2f}** minutes")
        st.write(f"Instructor finish: {inst['finish']:.2f} min")
        if exp_riders:
            st.write(f"First EXP start: {exp_riders[0]['start']:.2f}, last EXP finish: {last_exp:.2f} min")
        if foc_riders:
            st.write(f"First FOC start: {foc_riders[0]['start']:.2f}, last FOC finish: {last_foc:.2f} min")

        # Combine all riders for animation
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
            "{name:'Queue', x:20, w:60},"
            "{name:'A', x:100, w:150},"
            "{name:'B', x:260, w:150},"
            "{name:'C', x:420, w:150},"
            "{name:'Test', x:580, w:150},"
            "{name:'Exit', x:740, w:80}];\n"
            "const ypos = {INST:80, EXP:160, FOC:240};\n"
            "let t = 0; function draw(){\n"
            "  ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif';\n"
            "  regions.forEach(r=>{ ctx.strokeRect(r.x,40,r.w,260); ctx.fillText(r.name, r.x+5,30); });\n"
            "  timerDiv.innerText = 'Time: '+t.toFixed(2)+' min';\n"
            "  riders.forEach(r=>{ if(t < r.start) return; let e = t - r.start; let x, y = ypos[r.id.replace(/[0-9]/g,'')];\n"
            "    if(e < r.a){ x = regions[1].x + (e/r.a)*regions[1].w; }\n"
            "    else if(e < r.a + r.b){ e -= r.a; x = regions[2].x + (e/r.b)*regions[2].w; }\n"
            "    else if(e < r.a + r.b + r.c){ e -= (r.a + r.b); x = regions[3].x + (e/r.c)*regions[3].w; }\n"
            "    else if(e < r.a + r.b + r.c + r.test){ e -= (r.a + r.b + r.c); x = regions[4].x + (e/r.test)*regions[4].w; }\n"
            "    else if(e < r.a + r.b + r.c + r.test + exitDur){ e -= (r.a + r.b + r.c + r.test); x = regions[5].x + (e/exitDur)*regions[5].w; }\n"
            "    else{ x = regions[0].x + regions[0].w/2; }\n"
            "    ctx.beginPath(); ctx.fillStyle = r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue'; ctx.arc(x,y,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id, x-10,y+20); });\n"
            "  t += dt; if(t < totalTime + exitDur) requestAnimationFrame(draw); }\n"
            "draw();\n"
            "</script>"
        )
        components.html(html, height=400)

if __name__ == '__main__':
    main()
