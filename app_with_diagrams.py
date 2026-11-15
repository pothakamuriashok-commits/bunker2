import math
import io
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="RCC Square Bunker Design",
    page_icon="🏗️",
    layout="wide",
)

st.title("🏗️ RCC Square Bunker Design")
st.caption("Working Stress Method — based on the calculation program provided")

def make_sfd_bmd(pressure, span, member_name="Side Wall"):
    """Diagrammatic SFD/BMD for the uniform-pressure model used by the app."""
    x = [i * span / 100 for i in range(101)]
    w = pressure
    shear = [w * (span / 2 - xi) for xi in x]
    moment = [w * xi * (span - xi) / 2 for xi in x]

    fig_sfd, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(x, shear, linewidth=2)
    ax.axhline(0, linewidth=1)
    ax.fill_between(x, shear, 0, alpha=0.12)
    ax.set_title(f"{member_name} — Shear Force Diagram (SFD)")
    ax.set_xlabel("Distance along wall (m)")
    ax.set_ylabel("Shear force (kN)")
    ax.grid(True, alpha=0.25)

    fig_bmd, ax2 = plt.subplots(figsize=(9, 4.5))
    ax2.plot(x, moment, linewidth=2)
    ax2.axhline(0, linewidth=1)
    ax2.fill_between(x, moment, 0, alpha=0.12)
    ax2.set_title(f"{member_name} — Bending Moment Diagram (BMD)")
    ax2.set_xlabel("Distance along wall (m)")
    ax2.set_ylabel("Bending moment (kN·m)")
    ax2.grid(True, alpha=0.25)
    return fig_sfd, fig_bmd


def make_hopper_bmd(total_pressure, span):
    x = [i * span / 100 for i in range(101)]
    w = total_pressure
    moment = [w * xi * (span - xi) / 2 for xi in x]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(x, moment, linewidth=2)
    ax.axhline(0, linewidth=1)
    ax.fill_between(x, moment, 0, alpha=0.12)
    ax.set_title("Hopper — Bending Moment Diagram (schematic)")
    ax.set_xlabel("Effective hopper span (m)")
    ax.set_ylabel("Bending moment (kN·m/m)")
    ax.grid(True, alpha=0.25)
    return fig


def make_reinforcement_diagram(L, H, hopper_depth, outlet):
    fig, ax = plt.subplots(figsize=(10, 8))
    cx = L / 2
    ax.plot([0, L], [0, 0], linewidth=3)
    ax.plot([0, 0], [0, H], linewidth=3)
    ax.plot([L, L], [0, H], linewidth=3)
    ax.plot([0, L], [H, H], linewidth=2)
    ax.plot([0, cx-outlet/2], [0, -hopper_depth], linewidth=3)
    ax.plot([L, cx+outlet/2], [0, -hopper_depth], linewidth=3)
    ax.plot([cx-outlet/2, cx+outlet/2], [-hopper_depth, -hopper_depth], linewidth=3)

    for y in [0.35, 0.70, 1.05]:
        if y < H:
            ax.plot([0.08, L-0.08], [y, y], linestyle="--", linewidth=1.2)
    for x in [0.25, 0.55, 0.85, 1.15, 1.45, 1.75, 2.05, 2.35, 2.65]:
        if x < L:
            ax.plot([x, x], [0.10, H-0.10], linestyle=":", linewidth=1)

    ax.plot([0.12, cx-outlet/2-0.08], [-0.15, -hopper_depth+0.12], linestyle="--", linewidth=1.5)
    ax.plot([L-0.12, cx+outlet/2+0.08], [-0.15, -hopper_depth+0.12], linestyle="--", linewidth=1.5)

    ax.annotate("Corner: 12 mm @ 150 c/c", xy=(0.5, min(0.7,H-0.2)),
                xytext=(L+0.25, H-0.7), arrowprops=dict(arrowstyle="->"), fontsize=10)
    ax.annotate("Centre: 12 mm @ 300 c/c", xy=(L/2, min(1.1,H-0.2)),
                xytext=(L+0.25, H-1.5), arrowprops=dict(arrowstyle="->"), fontsize=10)
    ax.annotate("Hopper: 10 mm @ 260 c/c", xy=(cx, -hopper_depth/2),
                xytext=(L+0.25, -hopper_depth/2), arrowprops=dict(arrowstyle="->"), fontsize=10)

    ax.text(cx, H+0.18, f"RCC Square Bunker — {L:g} m × {L:g} m",
            ha="center", fontsize=12, fontweight="bold")
    ax.text(cx, -hopper_depth-0.55, f"Outlet = {outlet:g} m × {outlet:g} m",
            ha="center", fontsize=10)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.25, L+1.7)
    ax.set_ylim(-hopper_depth-0.8, H+0.5)
    ax.set_xlabel("Length (m)")
    ax.set_ylabel("Elevation (m)")
    ax.set_title("Schematic Reinforcement / Section Detail")
    ax.grid(True, alpha=0.18)
    return fig


def make_bbs(design):
    rows = [
        ["SW-C", "Side wall corner", 12, 150, "Main reinforcement", "Source-program value"],
        ["SW-M", "Side wall centre", 12, 300, "Centre reinforcement", "Source-program value"],
        ["HP-N", "Hopper negative zone", 10, round(design["spacing"]), "Top/negative reinforcement", "Calculated spacing"],
        ["HP-P", "Hopper positive zone", 10, round(design["spacing"]), "Bottom/positive reinforcement", "Calculated spacing"],
        ["EB", "Edge beam", "—", "—", "300 × 300 mm beam", "Beam reinforcement not calculated in source program"],
    ]
    return pd.DataFrame(rows, columns=["Mark", "Member", "Bar dia. (mm)", "Spacing (mm)", "Purpose", "Remarks"])


def calculate_design(
    coal_weight, density, L, B, H, hopper_depth, outlet,
    phi, theta, wall_t, hopper_t, cover,
    fck, fy, sigma_cbc, sigma_st, j, Q, m
):
    # 1. Dimensions
    required_volume = coal_weight / density
    surcharge_height = 0.86
    V_surcharge = L * B * surcharge_height / 3
    V_cubical = L * B * H
    V_hopper = (
        hopper_depth / 3 *
        (L * B + outlet**2 +
         math.sqrt(L**2 * B**2 * outlet**2))
    )
    total_volume = V_surcharge + V_cubical + V_hopper

    # 2. Side walls
    pressure = density * H * math.cos(math.radians(phi))**2
    effective_span = L + 0.18
    M_corner = pressure * effective_span**2 / 12
    T = pressure * L / 2
    d = wall_t - cover
    net_M_corner = M_corner - T * 0.06

    required_d = math.sqrt(
        net_M_corner * 1e6 / (Q * 1000)
    )

    Ast_corner = (
        net_M_corner * 1e6 /
        (sigma_st * j * d)
        + T * 1000 / sigma_st
    )

    M_centre = pressure * effective_span**2 / 24
    net_M_centre = M_centre - T * 0.06

    Ast_centre = (
        net_M_centre * 1e6 /
        (sigma_st * j * d)
        + T * 1000 / sigma_st
    )

    # 3. Side wall reinforcement
    minimum_wall_steel = 0.0012 * 1000 * wall_t
    corner_bar_area = math.pi * 12**2 / 4
    corner_spacing = corner_bar_area * 1000 / Ast_corner
    centre_spacing = corner_bar_area * 1000 / Ast_centre

    # 4. Hopper bottom
    slope_length = math.sqrt(1.25**2 + hopper_depth**2)
    hopper_weight = (
        (L + outlet) / 2 *
        slope_length *
        (4 * 0.18 * 24)
    )

    total_load = coal_weight + hopper_weight
    load_one_wall = total_load * 0.25
    theta_rad = math.radians(theta)
    cosec_theta = 1 / math.sin(theta_rad)
    direct_tension = load_one_wall * cosec_theta
    tension_per_m = direct_tension / L
    Ast_tension = tension_per_m * 1000 / sigma_st
    minimum_hopper_steel = 0.0012 * 1000 * hopper_t

    # 5. Normal pressure on hopper
    h = H + (0.5 * 1.2) + (0.5 * 0.86)
    phi_rad = math.radians(phi)

    pn = density * h * (
        math.cos(theta_rad)**2 +
        math.cos(phi_rad)**2 * math.sin(theta_rad)**2
    )

    self_weight_pressure = (
        0.18 * 24 * math.cos(theta_rad)
    )
    total_pressure = pn + self_weight_pressure

    # 6. Hopper bending moments
    effective_hopper_span = (L + outlet) / 2 + 0.18

    M_negative = (
        total_pressure * effective_hopper_span**2 / 12
    )
    M_positive = (
        total_pressure * effective_hopper_span**2 / 24
    )

    d_hopper = hopper_t - cover

    Ast_negative = (
        M_negative * 1e6 /
        (sigma_st * j * d_hopper)
    )
    Ast_positive = (
        M_positive * 1e6 /
        (sigma_st * j * d_hopper)
    )

    # 7. Hopper reinforcement
    bar_dia = 10
    bar_area = math.pi * bar_dia**2 / 4

    required_hopper_steel = max(
        Ast_negative,
        Ast_positive,
        minimum_hopper_steel
    )

    spacing = bar_area * 1000 / required_hopper_steel

    # 8. Edge beams
    edge_beam_width = 300
    edge_beam_depth = 300

    return locals()


# -----------------------------
# INPUT PANEL
# -----------------------------
with st.sidebar:
    st.header("Design Inputs")

    st.subheader("Loading")
    coal_weight = st.number_input("Coal weight (kN)", min_value=0.1, value=300.0, step=10.0)
    density = st.number_input("Coal density (kN/m³)", min_value=0.1, value=9.0, step=0.5)

    st.subheader("Bunker dimensions")
    L = st.number_input("Length L (m)", min_value=0.1, value=3.0, step=0.1)
    B = st.number_input("Width B (m)", min_value=0.1, value=3.0, step=0.1)
    H = st.number_input("Vertical wall height H (m)", min_value=0.1, value=3.0, step=0.1)

    st.subheader("Hopper")
    hopper_depth = st.number_input("Hopper depth (m)", min_value=0.1, value=1.2, step=0.1)
    outlet = st.number_input("Outlet size (m)", min_value=0.05, value=0.5, step=0.05)
    theta = st.number_input("Hopper inclination θ (degrees)", min_value=1.0, max_value=89.0, value=45.0, step=1.0)

    st.subheader("Material / geometry")
    phi = st.number_input("Angle of repose φ (degrees)", min_value=0.0, max_value=89.0, value=30.0, step=1.0)
    wall_t = st.number_input("Wall thickness (mm)", min_value=50.0, value=180.0, step=10.0)
    hopper_t = st.number_input("Hopper thickness (mm)", min_value=50.0, value=180.0, step=10.0)
    cover = st.number_input("Clear cover (mm)", min_value=5.0, value=30.0, step=5.0)

    st.subheader("Material grades")
    fck = st.number_input("Concrete fck (N/mm²)", min_value=1.0, value=15.0, step=1.0)
    fy = st.number_input("Steel fy (N/mm²)", min_value=1.0, value=415.0, step=5.0)

    st.subheader("Working stress constants")
    sigma_cbc = st.number_input("σcbc (N/mm²)", min_value=0.1, value=5.0, step=0.5)
    sigma_st = st.number_input("σst (N/mm²)", min_value=0.1, value=230.0, step=5.0)
    j = st.number_input("j", min_value=0.001, value=0.903, step=0.001, format="%.3f")
    Q = st.number_input("Q", min_value=0.001, value=0.659, step=0.001, format="%.3f")
    m = st.number_input("m", min_value=0.001, value=19.0, step=0.5)

    calculate = st.button("Calculate Design", type="primary", use_container_width=True)


# -----------------------------
# CALCULATION
# -----------------------------
if calculate or "design" not in st.session_state:
    try:
        if wall_t <= cover:
            st.error("Wall thickness must be greater than clear cover.")
            st.stop()

        if hopper_t <= cover:
            st.error("Hopper thickness must be greater than clear cover.")
            st.stop()

        design = calculate_design(
            coal_weight, density, L, B, H, hopper_depth, outlet,
            phi, theta, wall_t, hopper_t, cover,
            fck, fy, sigma_cbc, sigma_st, j, Q, m
        )
        st.session_state.design = design
    except Exception as e:
        st.error(f"Calculation error: {e}")
        st.stop()
else:
    design = st.session_state.design


# -----------------------------
# RESULTS
# -----------------------------
st.success("Design calculation completed.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📐 Bunker Dimensions",
    "🧱 Side Walls",
    "🔻 Hopper",
    "🏗️ Edge Beams",
    "📈 SFD / BMD",
    "🧱 Reinforcement Diagram",
    "📋 BBS",
    "📋 Final Summary",
])

with tab1:
    st.subheader("1. Dimensions of Bunker")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Required volume", f"{design['required_volume']:.2f} m³")
    c2.metric("Surcharge volume", f"{design['V_surcharge']:.2f} m³")
    c3.metric("Cubical volume", f"{design['V_cubical']:.2f} m³")
    c4.metric("Hopper volume", f"{design['V_hopper']:.2f} m³")

    st.metric("Total volume", f"{design['total_volume']:.2f} m³")

with tab2:
    st.subheader("2. Design of Side Walls")

    c1, c2, c3 = st.columns(3)
    c1.metric("Horizontal pressure", f"{design['pressure']:.2f} kN/m²")
    c2.metric("Effective span", f"{design['effective_span']:.2f} m")
    c3.metric("Direct tension", f"{design['T']:.3f} kN")

    data = {
        "Parameter": [
            "Corner BM",
            "Net corner BM",
            "Required depth",
            "Corner steel",
            "Centre BM",
            "Net centre BM",
            "Centre steel",
        ],
        "Value": [
            f"{design['M_corner']:.2f} kN-m",
            f"{design['net_M_corner']:.2f} kN-m",
            f"{design['required_d']:.2f} mm",
            f"{design['Ast_corner']:.2f} mm²/m",
            f"{design['M_centre']:.2f} kN-m",
            f"{design['net_M_centre']:.2f} kN-m",
            f"{design['Ast_centre']:.2f} mm²/m",
        ],
    }
    st.table(data)

    st.subheader("3. Side Wall Reinforcement")
    c1, c2, c3 = st.columns(3)
    c1.metric("Minimum steel", f"{design['minimum_wall_steel']:.2f} mm²/m")
    c2.metric("Calculated corner spacing", f"{design['corner_spacing']:.1f} mm")
    c3.metric("Calculated centre spacing", f"{design['centre_spacing']:.1f} mm")

    st.info(
        "Textbook reinforcement: Corner bars = 12 mm @ 150 mm c/c; "
        "Centre bars = 12 mm @ 300 mm c/c."
    )

with tab3:
    st.subheader("4. Design of Hopper Bottom")

    c1, c2, c3 = st.columns(3)
    c1.metric("Hopper weight", f"{design['hopper_weight']:.2f} kN")
    c2.metric("Total load", f"{design['total_load']:.2f} kN")
    c3.metric("Load on one wall", f"{design['load_one_wall']:.2f} kN")

    c1, c2, c3 = st.columns(3)
    c1.metric("Direct tension", f"{design['direct_tension']:.2f} kN")
    c2.metric("Tension / metre", f"{design['tension_per_m']:.2f} kN/m")
    c3.metric("Steel for direct tension", f"{design['Ast_tension']:.2f} mm²/m")

    st.subheader("5. Normal Pressure on Hopper")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Height h", f"{design['h']:.2f} m")
    c2.metric("Coal pressure", f"{design['pn']:.2f} kN/m²")
    c3.metric("Self-weight pressure", f"{design['self_weight_pressure']:.2f} kN/m²")
    c4.metric("Total pressure", f"{design['total_pressure']:.2f} kN/m²")

    st.subheader("6. Hopper Bending Moments")
    data = {
        "Parameter": [
            "Effective hopper span",
            "Negative BM",
            "Positive BM",
            "Negative steel",
            "Positive steel",
        ],
        "Value": [
            f"{design['effective_hopper_span']:.2f} m",
            f"{design['M_negative']:.2f} kN-m/m",
            f"{design['M_positive']:.2f} kN-m/m",
            f"{design['Ast_negative']:.2f} mm²/m",
            f"{design['Ast_positive']:.2f} mm²/m",
        ],
    }
    st.table(data)

    st.subheader("7. Hopper Reinforcement")
    c1, c2, c3 = st.columns(3)
    c1.metric("Required steel", f"{design['required_hopper_steel']:.2f} mm²/m")
    c2.metric("10 mm bar area", f"{design['bar_area']:.2f} mm²")
    c3.metric("Calculated spacing", f"{design['spacing']:.2f} mm")

    st.info("Textbook hopper reinforcement = 10 mm @ 260 mm c/c.")

with tab4:
    st.subheader("8. Edge Beams")

    c1, c2 = st.columns(2)
    c1.metric("Width", f"{design['edge_beam_width']} mm")
    c2.metric("Depth", f"{design['edge_beam_depth']} mm")

with tab5:
    st.subheader("SFD / BMD")
    st.info("The SFD/BMD plots use the same uniform lateral-pressure and effective-span model used in this calculation app. They are diagrammatic design plots, not a separate frame-analysis model.")
    fig_sfd, fig_bmd = make_sfd_bmd(design["pressure"], design["effective_span"], "Side Wall")
    c1, c2 = st.columns(2)
    with c1:
        st.pyplot(fig_sfd, use_container_width=True)
        b1=io.BytesIO(); fig_sfd.savefig(b1, format="png", dpi=220, bbox_inches="tight")
        st.download_button("Download Side Wall SFD", b1.getvalue(), "side_wall_sfd.png", "image/png", key="sfd")
    with c2:
        st.pyplot(fig_bmd, use_container_width=True)
        b2=io.BytesIO(); fig_bmd.savefig(b2, format="png", dpi=220, bbox_inches="tight")
        st.download_button("Download Side Wall BMD", b2.getvalue(), "side_wall_bmd.png", "image/png", key="bmd")
    st.subheader("Hopper BMD")
    hfig=make_hopper_bmd(design["total_pressure"], design["effective_hopper_span"])
    st.pyplot(hfig, use_container_width=True)

with tab6:
    st.subheader("Reinforcement Diagram")
    st.info("Schematic reinforcement/detailing view based on the reinforcement values in the supplied calculation program. It is not a fabrication/shop drawing.")
    rfig=make_reinforcement_diagram(L, H, hopper_depth, outlet)
    st.pyplot(rfig, use_container_width=True)
    br=io.BytesIO(); rfig.savefig(br, format="png", dpi=250, bbox_inches="tight")
    st.download_button("Download Reinforcement Diagram", br.getvalue(), "rcc_bunker_reinforcement_diagram.png", "image/png", key="reinforcement")

with tab7:
    st.subheader("Bar Bending Schedule (BBS)")
    st.info("The source program gives bar diameters and spacing, but does not calculate individual bar lengths, bends, hooks, laps, or cutting lengths. The BBS below therefore contains only schedule information supported by the source calculation.")
    bbs=make_bbs(design)
    st.dataframe(bbs, use_container_width=True, hide_index=True)
    st.download_button("Download BBS as CSV", bbs.to_csv(index=False).encode("utf-8"), "rcc_bunker_bbs.csv", "text/csv", key="bbs")
    st.subheader("Reinforcement Summary")
    st.write("**Side wall corner:** 12 mm @ 150 mm c/c")
    st.write("**Side wall centre:** 12 mm @ 300 mm c/c")
    st.write("**Hopper:** 10 mm @ 260 mm c/c (textbook value)")

with tab5:
    st.subheader("Final Design Summary")

    summary = {
        "Item": [
            "Bunker size",
            "Vertical wall height",
            "Hopper depth",
            "Outlet size",
            "Concrete grade",
            "Steel grade",
            "Side wall thickness",
            "Hopper thickness",
            "Corner reinforcement",
            "Centre reinforcement",
            "Hopper reinforcement",
            "Edge beams",
        ],
        "Design": [
            f"{L:g} m × {B:g} m",
            f"{H:g} m",
            f"{hopper_depth:g} m",
            f"{outlet:g} m × {outlet:g} m",
            f"M{fck:g}",
            f"Fe{fy:g}",
            f"{wall_t:g} mm",
            f"{hopper_t:g} mm",
            "12 mm @ 150 mm c/c",
            "12 mm @ 300 mm c/c",
            "10 mm @ 260 mm c/c",
            "300 × 300 mm",
        ],
    }

    st.table(summary)

    st.divider()
    st.warning(
        "This app reproduces the supplied calculation program. "
        "It is a calculation aid and should not be treated as a substitute "
        "for independent structural engineering review, applicable codes, "
        "load combinations, detailing checks, or professional approval."
    )

st.sidebar.markdown("---")
st.sidebar.caption("RCC Square Bunker Design")
