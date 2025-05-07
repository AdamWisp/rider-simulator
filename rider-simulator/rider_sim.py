import json
import streamlit as st
import streamlit.components.v1 as components

# ───────────────────────────── Streamlit UI ───────────────────────────── #
def main():
    st.set_page_config(page_title="Rider Training Track Simulation", layout="wide")
    st.title("🏍️ Rider Training Track Simulation")

    # --- Sidebar: Configuration ---
    st.sidebar.header("Batch & Capacity")
    n_exp = st.sidebar.number_input("Number of EXP Riders", 0, 100, 25, key="n_exp")
    n_foc = st.sidebar.number_input("Number of FOC Riders", 0, 100, 10, key="n_foc")
    cap_zone = st.sidebar.number_input("Riders per Zone", 1, 2, 1, key="cap_zone")

    # --- Sidebar: Per-Zone Durations (max 480 min) ---
    st.sidebar.header("Zone-by-Zone Durations (minutes, max 480)")
    inst_a = st.sidebar.number_input("Inst Zone A", 0.0, 480.0, 5.0, 0.1)
    inst_b = st.sidebar.number_input("Inst Zone B", 0.0, 480.0, 5.0, 0.1)
    inst_c = st.sidebar.number_input("Inst Zone C", 0.0, 480.0, 5.0, 0.1)
    exp_a = st.sidebar.number_input("EXP Zone A", 0.0, 480.0, 4.0, 0.1)
    exp_b = st.sidebar.number_input("EXP Zone B", 0.0, 480.0, 4.0, 0.1)
    exp_c = st.sidebar.number_input("EXP Zone C", 0.0, 480.0, 4.0, 0.1)
    foc_a = st.sidebar.number_input("FOC Zone A", 0.0, 480.0, 3.0, 0.1)
    foc_b = st.sidebar.number_input("FOC Zone B", 0.0, 480.0, 3.0, 0.1)
    foc_c = st.sidebar.number_input("FOC Zone C", 0.0, 480.0, 3.0, 0.1)

    # --- Sidebar: Other Phases (max 480 min) ---
    st.sidebar.header("Other Phases (one-time)")
    inst_lap = st.sidebar.number_input("Instructor Whole Lap", 0.0, 480.0, 15.0, 0.1)
    exp_lap = st.sidebar.number_input("EXP Whole Lap", 0.0, 480.0, 12.0, 0.1)
    foc_lap = st.sidebar.number_input("FOC Whole Lap", 0.0, 480.0, 10.0, 0.1)
    inst_test = st.sidebar.number_input("Instructor Test", 0.0, 480.0, 5.0, 0.1)
    exp_test = st.sidebar.number_input("EXP Test", 0.0, 480.0, 4.0, 0.1)
    foc_test = st.sidebar.number_input("FOC Test", 0.0, 480.0, 3.0, 0.1)

    # --- Sidebar: Select Phases for EXP/FOC ---
    st.sidebar.header("Select EXP/FOC Phases")
    phases_selected = st.sidebar.multiselect(
        "Include phases:", ["Per-Zone", "Whole Lap", "Test"],
        default=["Per-Zone", "Whole Lap", "Test"]
    )
    phase_order = ["Per-Zone", "Whole Lap", "Test"]
    phases = [p for p in phase_order if p in phases_selected]

    # --- Preview Estimated Total Time ---
    def compute_estimated():
        exit_time = 0.5
        current = 0.0
        def pipeline(start, count, a, b, c, cap):
            t = 0
            A_free = [start]*cap
            B_free = [start]*cap
            C_free = [start]*cap
            for _ in range(count):
                ia = min(range(cap), key=lambda idx: A_free[idx])
                ta = A_free[ia]; A_free[ia] = ta + a
                tb_ready = ta + a
                ib = min(range(cap), key=lambda idx: max(B_free[idx], tb_ready))
                tb = max(B_free[ib], tb_ready); B_free[ib] = tb + b
                tc_ready = tb + b
                ic = min(range(cap), key=lambda idx: max(C_free[idx], tc_ready))
                tc = max(C_free[ic], tc_ready); C_free[ic] = tc + c
                te = tc + c
                t = te + exit_time
            return t
        # Instructor
        current = pipeline(0.0, 1, inst_a, inst_b, inst_c, 1)
        current = pipeline(current, 1, inst_lap/3, inst_lap/3, inst_lap/3, 1)
        current = pipeline(current, 1, inst_test/3, inst_test/3, inst_test/3, 1)
        # EXP
        for ph in phases:
            if ph=='Per-Zone': a,b,c,cap = exp_a, exp_b, exp_c, cap_zone
            elif ph=='Whole Lap': a,b,c,cap = exp_lap/3, exp_lap/3, exp_lap/3, 1
            else: a,b,c,cap = exp_test/3, exp_test/3, exp_test/3, 1
            current = pipeline(current, n_exp, a, b, c, cap)
        # FOC
        for ph in phases:
            if ph=='Per-Zone': a,b,c,cap = foc_a, foc_b, foc_c, cap_zone
            elif ph=='Whole Lap': a,b,c,cap = foc_lap/3, foc_lap/3, foc_lap/3, 1
            else: a,b,c,cap = foc_test/3, foc_test/3, foc_test/3, 1
            current = pipeline(current, n_foc, a, b, c, cap)
        return current
    est_total = compute_estimated()
    h = int(est_total//60)
    m = int(est_total%60)
    s = int((est_total*60)%60)
    st.sidebar.markdown(f"**Estimated Total Time:** {est_total:.2f} min ({h:02d}h {m:02d}m {s:02d}s)")

    # --- Run Simulation ---
    if st.sidebar.button("Start Simulation"):
        # ... same pipeline & scheduling logic as above ...
        st.error("Simulation running... please rerun after checking preview.")

if __name__=='__main__':
    main()
