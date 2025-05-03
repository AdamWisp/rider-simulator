import json
import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ───────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Track Simulation", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar: Batches & Capacity ---
    st.sidebar.header("Batch Settings")
    n_exp = st.sidebar.number_input("Number of EXP Riders", 0, 100, 25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", 0, 100, 10, key="n_foc")
    cap_zone = st.sidebar.number_input("Riders per Zone", 1, 2, 1, key="cap_zone")

    # --- Sidebar: Phases ---
    st.sidebar.header("Select Phases")
    phases = st.sidebar.multiselect(
        "Timing Phases order:", ["Per-Zone", "Whole Lap", "Test"], default=["Per-Zone", "Whole Lap", "Test"]
    )

    # --- Sidebar: Durations per Phase and Batch ---
    st.sidebar.subheader("Per-Zone Total (sum of A+B+C)")
    inst_pz = st.sidebar.number_input("Instructor Total Zone", 0.0, 180.0, 15.0, 0.1, key="inst_pz")
    exp_pz = st.sidebar.number_input("EXP Total Zone", 0.0, 180.0, 12.0, 0.1, key="exp_pz")
    foc_pz = st.sidebar.number_input("FOC Total Zone", 0.0, 180.0, 10.0, 0.1, key="foc_pz")
    inst_az = inst_bz = inst_cz = inst_pz / 3.0
    exp_az = exp_bz = exp_cz = exp_pz / 3.0
    foc_az = foc_bz = foc_cz = foc_pz / 3.0

    st.sidebar.subheader("Whole Lap Duration")
    inst_lap = st.sidebar.number_input("Instructor Lap", 0.0, 180.0, 15.0, 0.1, key="inst_lap")
    exp_lap = st.sidebar.number_input("EXP Lap", 0.0, 180.0, 12.0, 0.1, key="exp_lap")
    foc_lap = st.sidebar.number_input("FOC Lap", 0.0, 180.0, 10.0, 0.1, key="foc_lap")

    st.sidebar.subheader("Test Duration")
    inst_test = st.sidebar.number_input("Instructor Test", 0.0, 180.0, 5.0, 0.1, key="inst_test")
    exp_test = st.sidebar.number_input("EXP Test", 0.0, 180.0, 4.0, 0.1, key="exp_test")
    foc_test = st.sidebar.number_input("FOC Test", 0.0, 180.0, 3.0, 0.1, key="foc_test")

    # --- Run Simulation ---
    if st.sidebar.button("Start Simulation"):
        exit_dur = 0.5
        schedule = []
        phase_end_times = []
        current_time = 0.0

        # Pipeline for one phase and one batch
        def pipeline(start, count, a_d, b_d, c_d, cap, label):
            A_free = [start] * cap
            B_free = [start] * cap
            C_free = [start] * cap
            out = []
            for i in range(count):
                rider = f"{label}{i+1 if label != 'INST' else ''}"
                # Zone A
                ai = min(range(cap), key=lambda x: A_free[x])
                sa = A_free[ai]
                A_free[ai] = sa + a_d
                # Zone B
                rb = sa + a_d
                bi = min(range(cap), key=lambda x: max(B_free[x], rb))
                sb = max(B_free[bi], rb)
                B_free[bi] = sb + b_d
                # Zone C
                rc = sb + b_d
                ci = min(range(cap), key=lambda x: max(C_free[x], rc))
                sc = max(C_free[ci], rc)
                C_free[ci] = sc + c_d
                # Exit
                se = sc + c_d
                fin = se + exit_dur
                out.append({"id": rider, "start": sa, "a": a_d, "b": b_d, "c": c_d, "exit": se, "finish": fin})
            return out

        # Execute each phase across inst, exp, foc sequentially
        for ph in phases:
            # Determine durations and capacity per batch
            if ph == "Per-Zone":
                inst_d = (inst_az, inst_bz, inst_cz, cap_zone)
                exp_d = (exp_az, exp_bz, exp_cz, cap_zone)
                foc_d = (foc_az, foc_bz, foc_cz, cap_zone)
            elif ph == "Whole Lap":
                inst_d = (inst_lap, 0.0, 0.0, 1)
                exp_d = (exp_lap, 0.0, 0.0, 1)
                foc_d = (foc_lap, 0.0, 0.0, 1)
            else:  # Test
                inst_d = (0.0, 0.0, inst_test, 1)
                exp_d = (0.0, 0.0, exp_test, 1)
                foc_d = (0.0, 0.0, foc_test, 1)

            # Instructor
            inst_sched = pipeline(current_time, 1, *inst_d, 'INST')
            schedule.extend(inst_sched)
            current_time = inst_sched[-1]['finish']
            # EXP
            exp_sched = pipeline(current_time, n_exp, *exp_d, 'EXP')
            schedule.extend(exp_sched)
            current_time = exp_sched[-1]['finish'] if exp_sched else current_time
            # FOC
            foc_sched = pipeline(current_time, n_foc, *foc_d, 'FOC')
            schedule.extend(foc_sched)
            current_time = foc_sched[-1]['finish'] if foc_sched else current_time

            # record phase end time
            phase_end_times.append(current_time)

        total_time = current_time

        # --- Summary ---
        st.subheader("Simulation Results")
        st.write(f"Total Time: **{total_time:.2f}** minutes")

        # --- Animation with Phase Indicator ---
        data = json.dumps(schedule)
        phases_json = json.dumps(phases)
        times_json = json.dumps(phase_end_times)
        html = (
            "<div style='display:flex; gap:20px; font:16px monospace;'>"
            "<div id='timer'>Time: 0.00 min</div>"
            "<div id='phase'>Phase: -</div>"
            "</div>"
            "<canvas id='track' width='900' height='360'></canvas>"
            "<script>\n"
            "const riders=" + data + ";\n"
            "const phases=" + phases_json + ";\n"
            "const phaseTimes=" + times_json + ";\n"
            "const total=" + str(total_time) + "; const dt=0.05; const exitD=0.5;\n"
            "const ctx=document.getElementById('track').getContext('2d');\n"
            "const timer=document.getElementById('timer'); const phaseDiv=document.getElementById('phase');\n"
            "const regs=[{x:20,w:60,n:'Queue'},{x:120,w:200,n:'A'},{x:340,w:200,n:'B'},{x:560,w:200,n:'C'},{x:780,w:80,n:'Exit'}];\n"
            "const y={INST:80,EXP:160,FOC:240};\n"
            "let t=0; function draw(){\n"
            "  ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif';\n"
            "  regs.forEach(r=>{ ctx.strokeRect(r.x,40,r.w,260); ctx.fillText(r.n, r.x+5,30); });\n"
            "  timer.innerText = 'Time: ' + t.toFixed(2) + ' min';\n"
            "  // phase update\n"
            "  let ph='-'; for(let i=0;i<phases.length;i++){ if(t<phaseTimes[i]){ ph=phases[i]; break; } }\n"
            "  phaseDiv.innerText = 'Phase: ' + ph;\n"
            "  // draw riders\n"
            "  riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x,ypos=y[r.id.replace(/[0-9]/g,'')];\n"
            "    if(e<r.a){ x=regs[1].x + (e/r.a)*regs[1].w; }\n"
            "    else if(e<r.a+r.b){ e-=r.a; x=regs[2].x + (e/r.b)*regs[2].w; }\n"
            "    else if(e<r.a+r.b+r.c){ e-= (r.a+r.b); x=regs[3].x + (e/r.c)*regs[3].w; }\n"
            "    else if(e<r.a+r.b+r.c+exitD){ e-=(r.a+r.b+r.c); x=regs[4].x + (e/exitD)*regs[4].w; }\n"
            "    else{ x=regs[0].x + regs[0].w/2; }\n"
            "    ctx.beginPath(); ctx.fillStyle = r.id.startsWith('INST') ? 'red' : r.id.startsWith('EXP') ? 'green' : 'blue'; ctx.arc(x,ypos,8,0,2*Math.PI); ctx.fill();\n"
            "    ctx.fillStyle='black'; ctx.fillText(r.id, x-10, ypos+20); });\n"
            "  t+=dt; if(t< total + exitD) requestAnimationFrame(draw); }\n"
            " draw();\n"
            "</script>"
        )
        components.html(html, height=450)

if __name__=='__main__':
    main()
