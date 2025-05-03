import json
import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ───────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Simulator", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar Configuration ---
    st.sidebar.header("Batch Settings")
    n_exp = st.sidebar.number_input("Number of EXP Riders", 0, 100, 25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", 0, 100, 10, key="n_foc")

    st.sidebar.header("Zone Capacity")
    cap_zone = st.sidebar.number_input("Riders per Zone", 1, 2, 1, key="cap_zone")

    st.sidebar.header("Timing Phases")
    phases = st.sidebar.multiselect(
        "Select phases:", ["Per-Zone", "Whole Lap", "Test"], default=["Per-Zone"]
    )

    # --- Timing Inputs per Phase ---
    # Per-Zone
    if "Per-Zone" in phases:
        st.sidebar.subheader("Per-Zone Durations (min)")
        inst_pz = st.sidebar.number_input("INST Zone (sum A+B+C)", 0.0, 180.0, 15.0, 0.1, key="inst_pz")
        exp_pz = st.sidebar.number_input("EXP Zone (sum A+B+C)", 0.0, 180.0, 12.0, 0.1, key="exp_pz")
        foc_pz = st.sidebar.number_input("FOC Zone (sum A+B+C)", 0.0, 180.0, 10.0, 0.1, key="foc_pz")
        # split evenly into three zones
        inst_a = inst_b = inst_c = inst_pz / 3.0
        exp_a = exp_b = exp_c = exp_pz / 3.0
        foc_a = foc_b = foc_c = foc_pz / 3.0
    else:
        inst_a = inst_b = inst_c = exp_a = exp_b = exp_c = foc_a = foc_b = foc_c = 0.0

    # Whole Lap
    if "Whole Lap" in phases:
        st.sidebar.subheader("Whole Lap Durations (min)")
        inst_lap = st.sidebar.number_input("INST Lap", 0.0, 180.0, 15.0, 0.1, key="inst_lap")
        exp_lap = st.sidebar.number_input("EXP Lap", 0.0, 180.0, 12.0, 0.1, key="exp_lap")
        foc_lap = st.sidebar.number_input("FOC Lap", 0.0, 180.0, 10.0, 0.1, key="foc_lap")
        # used as whole-lap phase durations
    else:
        inst_lap = exp_lap = foc_lap = 0.0

    # Test
    if "Test" in phases:
        st.sidebar.subheader("Test Durations (min)")
        inst_test = st.sidebar.number_input("INST Test", 0.0, 180.0, 5.0, 0.1, key="inst_test")
        exp_test = st.sidebar.number_input("EXP Test", 0.0, 180.0, 4.0, 0.1, key="exp_test")
        foc_test = st.sidebar.number_input("FOC Test", 0.0, 180.0, 3.0, 0.1, key="foc_test")
    else:
        inst_test = exp_test = foc_test = 0.0

    # --- Run Simulation ---
    if st.sidebar.button("Start Simulation"):
        exit_dur = 0.5  # return-to-queue time
        schedule = []  # list of rider events

        # pipeline function: uses zones A/B/C or for Test uses c_d=test duration
        def pipeline(start, count, a_d, b_d, c_d, cap, label):
            A_free = [start] * cap
            B_free = [start] * cap
            C_free = [start] * cap
            out = []
            for i in range(count):
                rid = f"{label}{i+1 if label!='INST' else ''}"
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
                se = sc + c_d  # exit start
                fin = se + exit_dur
                out.append({
                    "id": rid,
                    "start": sa,
                    "a": a_d,
                    "b": b_d,
                    "c": c_d,
                    "exit": se,
                    "finish": fin,
                })
            return out

        current = 0.0
        # iterate phases in chosen order
        for phase in phases:
            if phase == "Per-Zone":
                # INST
                inst = pipeline(current, 1, inst_a, inst_b, inst_c, cap_zone, 'INST')[0]
                schedule.append(inst)
                current = inst['finish']
                # EXP
                exp_r = pipeline(current, n_exp, exp_a, exp_b, exp_c, cap_zone, 'EXP')
                schedule.extend(exp_r)
                current = exp_r[-1]['finish'] if exp_r else current
                # FOC
                foc_r = pipeline(current, n_foc, foc_a, foc_b, foc_c, cap_zone, 'FOC')
                schedule.extend(foc_r)
                current = foc_r[-1]['finish'] if foc_r else current
            elif phase == "Whole Lap":
                # treat whole lap as one duration on Zone A
                inst = pipeline(current, 1, inst_lap, 0, 0, 1, 'INST')[0]
                schedule.append(inst); current = inst['finish']
                exp_r = pipeline(current, n_exp, exp_lap, 0, 0, 1, 'EXP'); schedule.extend(exp_r)
                current = exp_r[-1]['finish'] if exp_r else current
                foc_r = pipeline(current, n_foc, foc_lap, 0, 0, 1, 'FOC'); schedule.extend(foc_r)
                current = foc_r[-1]['finish'] if foc_r else current
            else:  # Test
                inst = pipeline(current, 1, 0, 0, inst_test, 1, 'INST')[0]
                schedule.append(inst); current = inst['finish']
                exp_r = pipeline(current, n_exp, 0, 0, exp_test, 1, 'EXP'); schedule.extend(exp_r)
                current = exp_r[-1]['finish'] if exp_r else current
                foc_r = pipeline(current, n_foc, 0, 0, foc_test, 1, 'FOC'); schedule.extend(foc_r)
                current = foc_r[-1]['finish'] if foc_r else current

        total_time = current

        # Summary
        st.subheader("Simulation Results")
        st.write(f"Total Time: **{total_time:.2f}** minutes")

        # Animation
        data = json.dumps(schedule)
        html = (
            "<div id='timer' style='font:16px monospace'>Time: 0.00 min</div>"
            "<canvas id='track' width='900' height='360'></canvas>"
            "<script>\n"
            "const riders=" + data + "; const total=" + str(total_time) + "; const dt=0.05; const exitD=0.5;\n"
            "const ctx=document.getElementById('track').getContext('2d'); const timer=document.getElementById('timer');\n"
            "const regs=[{x:20,w:60,n:'Que'},{x:120,w:200,n:'A'},{x:340,w:200,n:'B'},{x:560,w:200,n:'C'},{x:780,w:80,n:'Exit'}];\n"
            "const y={INST:80,EXP:160,FOC:240}; let t=0; function draw(){ ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif'; regs.forEach(r=>{ctx.strokeRect(r.x,40,r.w,260);ctx.fillText(r.n,r.x+5,30);}); timer.innerText='Time: '+t.toFixed(2)+' min'; riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x,ypos=y[r.id.replace(/[0-9]/g,'')]; if(e<r.a){ x=regs[1].x+e/r.a*regs[1].w; } else if(e<r.a+r.b){ e-=r.a; x=regs[2].x+e/r.b*regs[2].w; } else if(e<r.a+r.b+r.c){ e-=r.a+r.b; x=regs[3].x+e/r.c*regs[3].w; } else if(e<r.a+r.b+r.c+exitD){ e-=(r.a+r.b+r.c); x=regs[4].x+e/exitD*regs[4].w; } else { x=regs[0].x+regs[0].w/2; } ctx.beginPath(); ctx.fillStyle=r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue'; ctx.arc(x,ypos,8,0,2*Math.PI); ctx.fill(); ctx.fillStyle='black'; ctx.fillText(r.id,x-10,ypos+20);} ); t+=dt; if(t<total+exitD)requestAnimationFrame(draw);} draw();\n"
            "</script>"
        )
        components.html(html, height=400)

if __name__ == '__main__':
    main()
