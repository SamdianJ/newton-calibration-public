"""Render the README preview from archived measurements and predictions.

Run from the repository root:
    python -m pip install matplotlib
    python -m examples.cable_calibration.render_preview
No Newton simulation is performed.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CASE = Path(__file__).resolve().parent


def main():
    metrics = json.loads((CASE / "archive/expected-metrics.json").read_text())
    experiment = json.loads((CASE / "data/experiments.json").read_text())["noplug_release"]
    times = np.asarray(experiment["times"])
    reference = np.asarray(experiment["reference"])
    mask = np.asarray(experiment["mask"], dtype=bool)
    stages = ["Bstar", "C"]
    labels = ["Viscous model (B*)", "SLS model (C)"]
    colors = ["#527eb1", "#087e83"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "text.color": "#172e40",
            "axes.labelcolor": "#172e40",
        }
    )
    fig, (traces, bars) = plt.subplots(1, 2, figsize=(12, 5.4), gridspec_kw={"width_ratios": [1.8, 1]})
    fig.patch.set_facecolor("#f7f5ef")
    for ax in (bars, traces):
        ax.set_facecolor("#f7f5ef")
        ax.grid(axis="y", color="#dbe0e0", linewidth=0.7)
        ax.set_axisbelow(True)
    values = [metrics[f"{stage}__noplug_release"]["rmse_mm"] for stage in stages]
    bars.bar(["Viscous model\n(B*)", "SLS model\n(C)"], values, color=colors, width=0.58)
    for i, value in enumerate(values):
        bars.text(i, value + 0.05, f"{value:.3f}", ha="center", weight="bold")
    bars.set_ylim(0, 2.0)
    bars.set_ylabel("Coordinate RMSE (mm)")
    bars.set_title("Error across scored x/z channels", loc="left", pad=15, weight="bold")

    valid = mask[:, 29]
    traces.plot(
        times[valid],
        reference[valid, 29] * 1000,
        color="#172e40",
        linewidth=2.5,
        marker=".",
        label="Measured",
    )
    with np.load(CASE / "data/traces.npz", allow_pickle=False) as archive:
        for stage, color, label in zip(stages, colors, labels, strict=True):
            traces.plot(
                times[valid],
                archive[f"{stage}__noplug_release"][valid, 29] * 1000,
                color=color,
                linewidth=2,
                label=label,
            )
    traces.set_title("Vertical motion at 150 mm along the cable", loc="left", pad=15, weight="bold")
    traces.set_xlabel("Time after release (s)")
    traces.set_ylabel("z (mm)")
    traces.legend(frameon=False, loc="lower right", fontsize=9)
    fig.suptitle("Cable release experiment", x=0.065, y=0.965, ha="left", fontsize=19, weight="bold")
    fig.text(
        0.065,
        0.885,
        "Newton VBD · 17 cm free cable · no-plug experiment",
        fontsize=11,
        color="#50616e",
    )
    fig.text(
        0.065,
        0.105,
        "Scored release window: 28 frames, 30 x/z channels. Both models fitted to the same recording.",
        fontsize=10,
    )
    fig.text(
        0.065,
        0.055,
        "See the case study for model definitions, numerical checks, and validation scope.",
        fontsize=10,
        color="#50616e",
    )
    fig.subplots_adjust(left=0.075, right=0.97, top=0.78, bottom=0.25, wspace=0.36)
    output = CASE / "reports/cable_calibration_preview.png"
    fig.savefig(output, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(output)


if __name__ == "__main__":
    main()
