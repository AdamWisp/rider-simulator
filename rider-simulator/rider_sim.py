import json
import streamlit as st
import streamlit.components.v1 as components

# ────────────────────────────── Streamlit UI ────────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Simulator", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar Configuration ---
    st.sidebar.header("Batch Settings")
    n_exp = st.sidebar.number_input("Number of EXP Riders", 0, 100, 25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", 0, 100, 10, key="n_foc")

    st.sidebar.header("Zone Capacity")
    cap_zone = st.sidebar.number_input("Riders per Zone", 1, 2, 1, key="cap_zone")

    st.sidebar.header("Timing Mode")
    mode = st.sidebar.radio(
        "Choose timing:", ["Per-Zone", "Whole Lap", "Test"], index=0, key="timing_mode"
    )

    # --- Timing Inputs ---
    # Default durations initialized
    inst_a = inst_b = inst_c = exp_a = exp_b = exp_c = foc_a = foc_b = foc_c = 0.0
    inst_lap = exp_lap = foc_lap = test_inst = test_exp = test_foc = 0.0

    if mode == "Per-Zone":
        st.sidebar.subheader("Instructor Zone (min)")
        inst_a = st.sidebar.number_input("INST Zone A", 0.0, 60.0, 5.0, 0.1, key="inst_a")
        inst_b = st.sidebar.number_input("INST Zone B", 0.0, 60.0, 5.0, 0.1, key="inst_b")
        inst_c = st.sidebar.number_input("INST Zone C", 0.0, 60.0, 5.0, 0.1, key="inst_c")

        st.sidebar.subheader("EXP Zone (min)")
        exp_a = st.sidebar.number_input("EXP Zone A", 0.0, 60.0, 4.0, 0.1, key="exp_a")
        exp_b = st.sidebar.number_input("EXP Zone B", 0.0, 60.0, 4.0, 0.1, key="exp_b")
        exp_c = st.sidebar.number_input("EXP Zone C", 0.0, 60.0, 4.0, 0.1, key="exp_c")

        st.sidebar.subheader("FOC Zone (min)")
        foc_a = st.sidebar.number_input("FOC Zone A", 0.0, 60.0, 3.0, 0.1, key="foc_a")
        foc_b = st.sidebar.number_input("FOC Zone B", 0.0, 60.0, 3.0, 0.1, key="foc_b")
        foc_c = st.sidebar.number_input("FOC Zone C", 0.0, 60.0, 3.0, 0.1, key="foc_c")

    elif mode == "Whole Lap":
        st.sidebar.subheader("Whole Lap Duration (min)")
        inst_lap = st.sidebar.number_input("INST Lap", 0.0, 180.0, 15.0, 0.1, key="inst_lap")
        exp_lap = st.sidebar.number_input("EXP Lap", 0.0, 180.0, 12.0, 0.1, key="exp_lap")
        foc_lap = st.sidebar.number_input("FOC Lap", 0.0, 180.0, 10.0, 0.1, key="foc_lap")
        # split evenly
        inst_a = inst_b = inst_c = inst_lap / 3.0
        exp_a = exp_b = exp_c = exp_lap / 3.0
        foc_a = foc_b = foc_c = foc_lap / 3.0

    else:  # Test mode
        st.sidebar.subheader("Test Duration (min)")
        test_inst = st.sidebar.number_input("INST Test", 0.0, 180.0, 5.0, 0.1, key="test_inst")
        test_exp = st.sidebar.number_input("EXP Test", 0.0, 180.0, 4.0, 0.1, key="test_exp")
        test_foc = st.sidebar.number_input("FOC Test", 0.0, 180.0, 3.0, 0.1, key="test_foc")
        # In test mode, only one rider at a time and single duration covers whole path
        inst_a = exp_a = foc_a = test_inst if test_inst else 0.0
        inst_b = exp_b = foc_b = test_exp if test_exp else 0.0
        inst_c = exp_c = foc_c = test_foc if test_foc else 0.0
        cap_zone = 1

    # --- Run Simulation ---
    if st.sidebar.button("Start Simulation", key="run_sim"):
        exit_dur = 0.5

        # Scheduling pipeline respecting zone capacities
        def pipeline(start, count, a_d, b_d, c_d, cap, label):
            A_free = [start] * cap
            B_free = [start] * cap
            C_free = [start] * cap
            riders = []
            for i in range(count):
                rid = f"{label}{i+1 if label!='INST' else ''}"
                # A
                ai = min(range(cap), key=lambda x: A_free[x])
                sa = A_free[ai]
                A_free[ai] = sa + a_d
                # B
                ready_b = sa + a_d
                bi = min(range(cap), key=lambda x: max(B_free[x], ready_b))
                sb = max(B_free[bi], ready_b)
                B_free[bi] = sb + b_d
                # C
                ready_c = sb + b_d
                ci = min(range(cap), key=lambda x: max(C_free[x], ready_c))
                sc = max(C_free[ci], ready_c)
                C_free[ci] = sc + c_d
                # exit
                se = sc + c_d
                fin = se + exit_dur
                riders.append({"id":rid, "start":sa, "a":a_d, "b":b_d, "c":c_d, "exit":se, "finish":fin})
            return riders

        # Assemble
        inst = pipeline(0.0, 1, inst_a, inst_b, inst_c, cap_zone, 'INST')[0]
        exp_list = pipeline(inst['finish'] + exit_dur, n_exp, exp_a, exp_b, exp_c, cap_zone, 'EXP')
        foc_list = pipeline((exp_list[-1]['finish'] if exp_list else inst['finish']) + exit_dur,
                             n_foc, foc_a, foc_b, foc_c, cap_zone, 'FOC')
        all_riders = [inst] + exp_list + foc_list
        total = all_riders[-1]['finish'] if all_riders else 0.0

        # Summary
        st.subheader("Simulation Results")
        st.write(f"Total Time: **{total:.2f}** min")
        st.write(f"INST finish: {inst['finish']:.2f} min")
        if exp_list: st.write(f"Last EXP finish: {exp_list[-1]['finish']:.2f} min")
        if foc_list: st.write(f"Last FOC finish: {foc_list[-1]['finish']:.2f} min")

        # Animation
        data = json.dumps(all_riders)
        html = (
            "<div id='timer' style='font:16px monospace'>Time: 0.00 min</div>"
            "<canvas id='track' width='900' height='360'></canvas>"
            "<script>\n"
            "const riders="+data+"; const total="+str(total)+"; const dt=0.05; const exitD=0.5;\n"
            "const ctx=document.getElementById('track').getContext('2d'); const timer=document.getElementById('timer');\n"
            "const regs=[{x:20,w:60,n:'Que'},{x:120,w:200,n:'A'},{x:340,w:200,n:'B'},{x:560,w:200,n:'C'},{x:780,w:80,n:'Exit'}];\n"
            "const y={INST:80,EXP:160,FOC:240}; let t=0; function draw(){ ctx.clearRect(0,0,900,360); ctx.font='14px sans-serif'; regs.forEach(r=>{ctx.strokeRect(r.x,40,r.w,260);ctx.fillText(r.n,r.x+5,30);}); timer.innerText='Time: '+t.toFixed(2)+' min'; riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x,ypos=y[r.id.replace(/[0-9]/g,'')]; if(e<r.a){x=regs[1].x+e/r.a*regs[1].w;} else if(e<r.a+r.b){e-=r.a;x=regs[2].x+e/r.b*regs[2].w;} else if(e<r.a+r.b+r.c){e-=r.a+r.b;x=regs[3].x+e/r.c*regs[3].w;} else if(e<r.a+r.b+r.c+exitD){e-=(r.a+r.b+r.c);x=regs[4].x+e/exitD*regs[4].w;} else{x=regs[0].x+regs[0].w/2;} ctx.beginPath();ctx.fillStyle=r.id.startsWith('INST')?'red':r.id.startsWith('EXP')?'green':'blue';ctx.arc(x,ypos,8,0,2*Math.PI);ctx.fill();ctx.fillStyle='black';ctx.fillText(r.id,x-10,ypos+20);} ); t+=dt;if(t<total+exitD)requestAnimationFrame(draw);}draw();\n"
            "</script>"
        )
        components.html(html, height=400)

if __name__=='__main__': main()
