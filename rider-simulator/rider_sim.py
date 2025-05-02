import json
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ────────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Simulator", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar Inputs ---
    st.sidebar.header("Batch Sizes")
    n_exp = st.sidebar.number_input("Number of EXP Riders", min_value=0, max_value=100,
                                     value=25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", min_value=0, max_value=100,
                                     value=10, key="n_foc")

    st.sidebar.header("Instructor Zone Times (min)")
    inst_a = st.sidebar.number_input("Instructor Zone A", 0.0, 60.0, 5.0, 0.1,
                                     key="inst_a")
    inst_b = st.sidebar.number_input("Instructor Zone B", 0.0, 60.0, 5.0, 0.1,
                                     key="inst_b")
    inst_c = st.sidebar.number_input("Instructor Zone C", 0.0, 60.0, 5.0, 0.1,
                                     key="inst_c")
    inst_lap = st.sidebar.number_input("Instructor Whole Lap", 0.0, 120.0, 10.0, 0.1,
                                        key="inst_lap")

    st.sidebar.header("EXP Zone Times (min)")
    exp_a = st.sidebar.number_input("EXP Zone A", 0.0, 60.0, 4.0, 0.1,
                                    key="exp_a")
    exp_b = st.sidebar.number_input("EXP Zone B", 0.0, 60.0, 4.0, 0.1,
                                    key="exp_b")
    exp_c = st.sidebar.number_input("EXP Zone C", 0.0, 60.0, 4.0, 0.1,
                                    key="exp_c")
    exp_lap = st.sidebar.number_input("EXP Whole Lap", 0.0, 120.0, 8.0, 0.1,
                                       key="exp_lap")

    st.sidebar.header("FOC Zone Times (min)")
    foc_a = st.sidebar.number_input("FOC Zone A", 0.0, 60.0, 3.0, 0.1,
                                    key="foc_a")
    foc_b = st.sidebar.number_input("FOC Zone B", 0.0, 60.0, 3.0, 0.1,
                                    key="foc_b")
    foc_c = st.sidebar.number_input("FOC Zone C", 0.0, 60.0, 3.0, 0.1,
                                    key="foc_c")
    foc_lap = st.sidebar.number_input("FOC Whole Lap", 0.0, 120.0, 6.0, 0.1,
                                       key="foc_lap")

    # Run simulation button
    if st.sidebar.button("Start Simulation", key="start_sim"):
        # Compute finish times
        inst_finish = inst_a + inst_b + inst_c + inst_lap
        exp_finish = inst_finish + exp_lap  # concurrency: all EXP start at inst_finish
        foc_finish = exp_finish + foc_lap    # all FOC start at exp_finish
        total_time = foc_finish

        # Build riders list
        riders = []
        # Instructor
        riders.append({"id": "INST-1", "start": 0.0,
                       "a": inst_a, "b": inst_b, "c": inst_c, "lap": inst_lap})
        # EXP batch concurrency
        for i in range(1, n_exp+1):
            riders.append({"id": f"EXP-{i}", "start": inst_finish,
                           "a": exp_a, "b": exp_b, "c": exp_c, "lap": exp_lap})
        # FOC batch concurrency
        for i in range(1, n_foc+1):
            riders.append({"id": f"FOC-{i}", "start": exp_finish,
                           "a": foc_a, "b": foc_b, "c": foc_c, "lap": foc_lap})

        # Display summary
        st.subheader("Simulation Results")
        st.write(f"Total Elapsed Time: **{total_time:.2f} minutes**")
        st.write(f"Instructor finished at: {inst_finish:.2f} min")
        if n_exp>0: st.write(f"EXP batch started at {inst_finish:.2f}, lap={exp_lap:.2f}, finished at: {exp_finish:.2f} min")
        if n_foc>0: st.write(f"FOC batch started at {exp_finish:.2f}, lap={foc_lap:.2f}, finished at: {foc_finish:.2f} min")

        # Animation via HTML5 Canvas
        riders_json = json.dumps(riders)
        html = (
            "<div style='font:16px monospace;' id='timer'>Time: 0.00 min</div>"
            "<canvas id='trackCanvas' width='960' height='260'></canvas>"
            "<script>\n"
            "const riders = " + riders_json + ";\n"
            "const totalTime = " + str(total_time) + ";\n"
            "const dt = 0.05; const exitDur=0.5;\n"
            "const canvas = document.getElementById('trackCanvas');\n"
            "const ctx = canvas.getContext('2d');\n"
            "const timerDiv = document.getElementById('timer');\n"
            "const regions = ["
            "{name:'Queue',x0:20,width:80},"
            "{name:'A',x0:120,width:150},"
            "{name:'B',x0:280,width:150},"
            "{name:'C',x0:440,width:150},"
            "{name:'Lap',x0:600,width:200},"
            "{name:'Exit',x0:820,width:80}];\n"
            "const yPos={INST:60,EXP:140,FOC:220};\n"
            "let t=0; function draw(){\n"
            "  ctx.clearRect(0,0,960,260);\n  ctx.font='14px sans-serif';\n  regions.forEach(r=>{ ctx.fillText(r.name,r.x0+10,30); ctx.strokeRect(r.x0,40,r.width,180); });\n"
            "  timerDiv.innerText='Time: '+t.toFixed(2)+' min';\n"
            "  riders.forEach(r=>{ if(t<r.start) return; let e=t-r.start; let x,y=yPos[r.id.split('-')[0]];\n"
            "    if(e<r.a){ x=regions[1].x0+(e/r.a)*regions[1].width; }\n"
            "    else if(e<r.a+r.b){ e-=r.a; x=regions[2].x0+(e/r.b)*regions[2].width; }\n"
            "    else if(e<r.a+r.b+r.c){ e-=r.a+r.b; x=regions[3].x0+(e/r.c)*regions[3].width; }\n"
            "    else if(e<r.a+r.b+r.c+r.lap){ e-=r.a+r.b+r.c; x=regions[4].x0+(e/r.lap)*regions[4].width; }\n"
            "    else if(e<r.a+r.b+r.c+r.lap+exitDur){ e-=r.a+r.b+r.c+r.lap; x=regions[5].x0+(e/exitDur)*regions[5].width; }\n"
            "    else{ x=regions[0].x0+regions[0].width/2; }\n"
            "    ctx.beginPath(); ctx.arc(x,y,6,0,2*Math.PI);\n"
            "    ctx.fillStyle=r.id.startsWith('INST')?'#ff0000':r.id.startsWith('EXP')?'#00aa00':'#0000ff'; ctx.fill();\n    ctx.fillStyle='#000'; ctx.fillText(r.id.split('-')[0],x-5,y+25); });\n"
            "  t+=dt; if(t<totalTime+1) requestAnimationFrame(draw); }\n draw();\n"
            "</script>"
        )
        components.html(html, height=320)

if __name__=='__main__':
    main()
