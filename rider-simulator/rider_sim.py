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
    # Per-Zone durations (split evenly later)
    st.sidebar.subheader("Per-Zone Total (sum of A+B+C)")
    inst_pz = st.sidebar.number_input("Instructor Total Zone", 0.0, 180.0, 15.0, 0.1, key="inst_pz")
    exp_pz = st.sidebar.number_input("EXP Total Zone", 0.0, 180.0, 12.0, 0.1, key="exp_pz")
    foc_pz = st.sidebar.number_input("FOC Total Zone", 0.0, 180.0, 10.0, 0.1, key="foc_pz")
    # split
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

        # Pipeline schedules one phase: zones A/B/C or test as c_d
        def pipeline(start, count, a_d, b_d, c_d, cap, label):
            A_free = [start] * cap
            B_free = [start] * cap
            C_free = [start] * cap
            out = []
            for i in range(count):
                rider = f"{label}{i+1 if label!='INST' else ''}"
                ai = min(range(cap), key=lambda x: A_free[x])
                sa = A_free[ai]
                A_free[ai] = sa + a_d
                rb = sa + a_d
                bi = min(range(cap), key=lambda x: max(B_free[x], rb))
                sb = max(B_free[bi], rb)
                B_free[bi] = sb + b_d
                rc = sb + b_d
                ci = min(range(cap), key=lambda x: max(C_free[x], rc))
                sc = max(C_free[ci], rc)
                C_free[ci] = sc + c_d
                se = sc + c_d
                fin = se + exit_dur
                out.append({"id": rider, "start": sa, "a": a_d, "b": b_d, "c": c_d, "exit": se, "finish": fin})
            return out

        # Helper to run phases for a batch
        def run_batch(start_time, count, label):
            current = start_time
            batch_sched = []
            for ph in phases:
                if ph == "Per-Zone":
                    a, b, c = (inst_az, inst_bz, inst_cz) if label=='INST' else (exp_az, exp_bz, exp_cz) if label=='EXP' else (foc_az, foc_bz, foc_cz)
                    cap = cap_zone
                elif ph == "Whole Lap":
                    lap = inst_lap if label=='INST' else exp_lap if label=='EXP' else foc_lap
                    a, b, c = lap, 0.0, 0.0
                    cap = 1
                else:  # Test
                    tst = inst_test if label=='INST' else exp_test if label=='EXP' else foc_test
                    a, b, c = 0.0, 0.0, tst
                    cap = 1
                phase_sched = pipeline(current, count, a, b, c, cap, label)
                batch_sched.extend(phase_sched)
                current = phase_sched[-1]['finish'] if phase_sched else current
            return batch_sched, current

        # Run instructor, EXP, then FOC
        inst_sched, t1 = run_batch(0.0, 1, 'INST')
        exp_sched, t2 = run_batch(t1, n_exp, 'EXP')
        foc_sched, t3 = run_batch(t2, n_foc, 'FOC')
        schedule = inst_sched + exp_sched + foc_sched
        total_time = t3

        # Summary
        st.subheader("Simulation Results")
        st.write(f"Total Time: **{total_time:.2f}** minutes")

        # Animation
        data = json.dumps(schedule)
        html = (
            "<div id='timer' style='font:16px monospace'>Time: 0.00 min</div>"
            "<canvas id='track' width='900' height='360'></canvas>"
            "<script>\n"
            "const riders="+data+"; const total="+str(total_time)+"; const dt=0.05; const exitD=0.5;\n"
            "const ctx=document.getElementById('track').getContext('2d'); const timer=document.getElementById('timer');\n"
            "const regs=[{x:20,w:60,n:'Que'},{x:120,w:200,n:'A'},{x:340,w:200,n:'B'},{x:560,w:200,n:'C'},{x:780,w:80,n:'Exit'}];\n"
            "const y={INST:80,EXP:160,FOC:240}; let t=0; function draw(){ ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif'; regs.forEach(r=>{ctx.strokeRect(r.x,40,r.w,260);ctx.fillText(r.n,r.x+5,30);}); timer.innerText='Time: '+t.toFixed(2)+' min'; riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x,ypos=y[r.id.replace(/[0-9]/g,'')]; if(e<r.a){ x=regs[1].x+e/r.a*regs[1].w; } else if(e<r.a+r.b){ e-=r.a; x=regs[2].x+e/r.b*regs[2].w; } else if(e<r.a+r.b+r.c){ e-=r.a+r.b; x=regs[3].x+e/r.c*regs[3].w; } else if(e<r.a+r.b+r.c+exitD){ e-=(r.a+r.b+r.c); x=regs[4].x+e/exitD*regs[4].w; } else { x=regs[0].x+regs[0].w/2; } ctx.beginPath(); ctx.fillStyle=r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue'; ctx.arc(x,ypos,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id,x-10,ypos+20);} ); t+=dt; if(t<total+exitD)requestAnimationFrame(draw);} draw();\n"
            "</script>"
        )
        components.html(html, height=400)

if __name__=='__main__':
    main()
