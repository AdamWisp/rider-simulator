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
    st.sidebar.header("Select Phases for EXP/FOC")
    phases = st.sidebar.multiselect(
        "Timing Phases order:", ["Per-Zone", "Whole Lap", "Test"], default=["Per-Zone", "Whole Lap", "Test"]
    )

    # --- Sidebar: Durations per Phase and Batch ---
    # Per-Zone totals (split evenly later)
    st.sidebar.subheader("Per-Zone Total (sum A+B+C)")
    inst_pz = st.sidebar.number_input("Instructor Total Zone", 0.0, 180.0, 15.0, 0.1, key="inst_pz")
    exp_pz = st.sidebar.number_input("EXP Total Zone", 0.0, 180.0, 12.0, 0.1, key="exp_pz")
    foc_pz = st.sidebar.number_input("FOC Total Zone", 0.0, 180.0, 10.0, 0.1, key="foc_pz")
    inst_az = inst_bz = inst_cz = inst_pz / 3.0
    exp_az = exp_bz = exp_cz = exp_pz / 3.0
    foc_az = foc_bz = foc_cz = foc_pz / 3.0

    # Whole Lap durations
    st.sidebar.subheader("Whole Lap Duration")
    inst_lap = st.sidebar.number_input("Instructor Lap", 0.0, 180.0, 15.0, 0.1, key="inst_lap")
    exp_lap = st.sidebar.number_input("EXP Lap", 0.0, 180.0, 12.0, 0.1, key="exp_lap")
    foc_lap = st.sidebar.number_input("FOC Lap", 0.0, 180.0, 10.0, 0.1, key="foc_lap")

    # Test durations
    st.sidebar.subheader("Test Duration")
    inst_test = st.sidebar.number_input("Instructor Test", 0.0, 180.0, 5.0, 0.1, key="inst_test")
    exp_test = st.sidebar.number_input("EXP Test", 0.0, 180.0, 4.0, 0.1, key="exp_test")
    foc_test = st.sidebar.number_input("FOC Test", 0.0, 180.0, 3.0, 0.1, key="foc_test")

    # --- Run Simulation ---
    if st.sidebar.button("Start Simulation"):
        exit_dur = 0.5
        schedule = []
        phase_end_times = []
        phase_sequence = []

        # Pipeline for one phase and one batch
        def pipeline(start, count, a_d, b_d, c_d, cap, label):
            A_free = [start] * cap
            B_free = [start] * cap
            C_free = [start] * cap
            out = []
            for i in range(count):
                rider_id = f"{label}{i+1 if label != 'INST' else ''}"
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
                out.append({
                    "id": rider_id,
                    "start": sa,
                    "a": a_d,
                    "b": b_d,
                    "c": c_d,
                    "exit": se,
                    "finish": fin
                })
            return out

        # 1) Instructor whole lap once
        inst_sched = pipeline(0.0, 1, inst_lap, 0.0, 0.0, 1, 'INST')
        schedule.extend(inst_sched)
        current_time = inst_sched[0]['finish']
        phase_end_times.append(current_time)
        phase_sequence.append({"batch": "INST", "phase": "Whole Lap"})

        # 2) EXP batch: all selected phases
        for ph in phases:
            if ph == "Per-Zone":
                a_d, b_d, c_d, cap = exp_az, exp_bz, exp_cz, cap_zone
            elif ph == "Whole Lap":
                a_d, b_d, c_d, cap = exp_lap, 0.0, 0.0, 1
            else:  # Test
                a_d, b_d, c_d, cap = 0.0, 0.0, exp_test, 1
            batch_sched = pipeline(current_time, n_exp, a_d, b_d, c_d, cap, 'EXP')
            schedule.extend(batch_sched)
            current_time = batch_sched[-1]['finish'] if batch_sched else current_time
            phase_end_times.append(current_time)
            phase_sequence.append({"batch": "EXP", "phase": ph})

        # 3) FOC batch: after EXP fully done
        for ph in phases:
            if ph == "Per-Zone":
                a_d, b_d, c_d, cap = foc_az, foc_bz, foc_cz, cap_zone
            elif ph == "Whole Lap":
                a_d, b_d, c_d, cap = foc_lap, 0.0, 0.0, 1
            else:
                a_d, b_d, c_d, cap = 0.0, 0.0, foc_test, 1
            batch_sched = pipeline(current_time, n_foc, a_d, b_d, c_d, cap, 'FOC')
            schedule.extend(batch_sched)
            current_time = batch_sched[-1]['finish'] if batch_sched else current_time
            phase_end_times.append(current_time)
            phase_sequence.append({"batch": "FOC", "phase": ph})

        total_time = current_time

        # --- Summary ---
        st.subheader("Simulation Results")
        st.write(f"Total Time: **{total_time:.2f}** minutes")

        # --- Animation with Batch & Phase Indicator ---
        data = json.dumps(schedule)
        seq_json = json.dumps(phase_sequence)
        times_json = json.dumps(phase_end_times)
        html = (
            "<div style='display:flex; gap:20px; font:16px monospace;'>"
            "<div id='timer'>Time: 0.00 min</div>"
            "<div id='indicator'>Phase: INST - Whole Lap</div>"
            "</div>"
            "<canvas id='track' width='900' height='360'></canvas>"
            "<script>\n"
            "const riders=" + data + ";\n"
            "const seq=" + seq_json + ";\n"
            "const times=" + times_json + ";\n"
            "const total=" + str(total_time) + ";\n"
            "const dt=0.05, exitD=0.5;\n"
            "const ctx=document.getElementById('track').getContext('2d');\n"
            "const timer=document.getElementById('timer'); const ind=document.getElementById('indicator');\n"
            "const regs=[{x:20,w:60,n:'Queue'},{x:120,w:200,n:'A'},{x:340,w:200,n:'B'},{x:560,w:200,n:'C'},{x:780,w:80,n:'Exit'}];\n"
            "const y={INST:80,EXP:160,FOC:240};\n"
            "let t=0; function draw(){\n"
            "  ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif';\n"
            "  regs.forEach(r=>{ ctx.strokeRect(r.x,40,r.w,260); ctx.fillText(r.n, r.x+5,30); });\n"
            "  timer.innerText='Time: '+t.toFixed(2)+' min';\n"
            "  // update indicator\n"
            "  for(let i=0;i<times.length;i++){ if(t<times[i]){ ind.innerText='Phase: '+seq[i].batch+' - '+seq[i].phase; break; }}\n"
            "  // draw riders\n"
            "  riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x,ypos=y[r.id.replace(/[0-9]/g,'')];\n"
            "    if(e<r.a){ x=regs[1].x+e/r.a*regs[1].w; }\n"
            "    else if(e<r.a+r.b){ e-=r.a; x=regs[2].x+e/r.b*regs[2].w; }\n"
            "    else if(e<r.a+r.b+r.c){ e-=(r.a+r.b); x=regs[3].x+e/r.c*regs[3].w; }\n"
            "    else if(e<r.a+r.b+r.c+exitD){ e-=(r.a+r.b+r.c); x=regs[4].x+e/exitD*regs[4].w; }\n"
            "    else{ x=regs[0].x+regs[0].w/2;} ctx.beginPath();ctx.fillStyle=r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue';ctx.arc(x,ypos,8,0,2*Math.PI);ctx.fill();ctx.fillStyle='black';ctx.fillText(r.id,x-10,ypos+20); });\n"
            "  t+=dt; if(t<total+exitD)requestAnimationFrame(draw); } draw();\n"
            "</script>"
        )
        components.html(html, height=450)

if __name__=='__main__':
    main()
