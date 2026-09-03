from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
import edf_preprocessor
import psd_math


EXCLUDED_HEADER_START = "EKG"
EXCLUDED_HEADER_END = "Pleth"
ANALYSIS_ON = "ANALYSIS_ON"
ANALYSIS_OFF = "ANALYSIS_OFF"
ROBUST_COLORBAR_TITLE = (
    "Linear PSD color scale\n"
    "(clipped to channel-wide\n"
    "5th-95th percentiles)"
)
PSD_SPECTRUM_COLORMAP = LinearSegmentedColormap.from_list(
    "psd_visible_spectrum",
    [
        "#8F00FF",  # violet: lower in-range PSD
        "#0000FF",  # blue
        "#00A000",  # green
        "#FFFF00",  # yellow
        "#FF7F00",  # orange
        "#FF0000",  # red: higher in-range PSD
    ],
)
PSD_SPECTRUM_COLORMAP.set_under("#000000")  # below 5th percentile
PSD_SPECTRUM_COLORMAP.set_over("#FFFFFF")  # above 95th percentile


## 1. analysis EDF input
def validate_analysis_edf_input(directory: str, file_name: str) -> tuple[Path, str]:
    directory_path = Path(directory.strip().strip('"')).expanduser()
    file_name = file_name.strip().strip('"')
    if not directory_path.is_dir():
        raise NotADirectoryError(f"Directory does not exist: {directory_path}")
    if Path(file_name).name != file_name:
        raise ValueError("Enter the file name only, without a directory")
    if Path(file_name).suffix.lower() != ".edf":
        raise ValueError("The file name must include the .edf extension")

    edf_path = directory_path / file_name
    if not edf_path.is_file():
        raise FileNotFoundError(f"EDF file does not exist: {edf_path}")
    return directory_path.resolve(), file_name


def validate_output_directory(directory: str) -> Path:
    directory = directory.strip().strip('"')
    if not directory:
        raise ValueError("Output directory is empty")

    output_directory = Path(directory).expanduser()
    if output_directory.exists() and not output_directory.is_dir():
        raise NotADirectoryError(
            f"Output path is not a directory: {output_directory}"
        )
    return output_directory.resolve()


def get_analysis_edf_input() -> tuple[Path, str, Path]:
    root = tk.Tk()
    root.withdraw()
    try:
        while True:
            directory = simpledialog.askstring("Analysis EDF", "1. Directory", parent=root)
            if directory is None:
                raise SystemExit("EDF input cancelled")
            file_name = simpledialog.askstring("Analysis EDF", "2. File name (including .edf)",parent=root)
            if file_name is None:
                raise SystemExit("EDF input cancelled")
            output_directory = simpledialog.askstring(
                "Figure output",
                "3. Figure output directory",
                parent=root,
            )
            if output_directory is None:
                raise SystemExit("Figure output input cancelled")
            try:
                analysis_directory, analysis_file_name = validate_analysis_edf_input(
                    directory,
                    file_name,
                )
                validated_output_directory = validate_output_directory(
                    output_directory
                )
                return (
                    analysis_directory,
                    analysis_file_name,
                    validated_output_directory,
                )
            except (ValueError, OSError) as error:
                messagebox.showerror("Invalid EDF input", str(error), parent=root)
    finally:
        root.destroy()


## 2. figure-generation header selection
def enumerate_excluded_headers(header_names: list[str], start_header: str = EXCLUDED_HEADER_START, end_header: str = EXCLUDED_HEADER_END) -> list[tuple[int, str]]:
    indexed_headers = list(enumerate(header_names))
    try:
        start_index = header_names.index(start_header)
        end_index = header_names.index(end_header)
    except ValueError as error:
        raise ValueError(f"Required exclusion header is missing: {error}") from error
    if start_index > end_index:
        raise ValueError(f"{start_header} must precede {end_header}")
    return indexed_headers[start_index : end_index + 1]


def enumerate_figure_headers(header_names: list[str]) -> list[tuple[int, str]]:
    excluded_headers = enumerate_excluded_headers(header_names)
    excluded_indices = {index for index, _ in excluded_headers}
    return [(index, header_name) for index, header_name in enumerate(header_names) if index not in excluded_indices]


## 3. PSD figure generation
def get_welch_averaging_method() -> str:
    root = tk.Tk()
    root.title("Welch averaging")
    root.resizable(False, False)
    selection: dict[str, str | None] = {"value": None}
    selected_method = tk.StringVar(value="median")

    ttk.Label(root, text="Select Welch averaging method:").grid(
        row=0, column=0, padx=16, pady=(16, 8)
    )
    method_dropdown = ttk.Combobox(
        root,
        textvariable=selected_method,
        values=("median", "mean"),
        state="readonly",
        width=12,
    )
    method_dropdown.grid(row=1, column=0, padx=16, pady=8)
    method_dropdown.current(0)

    def confirm_selection() -> None:
        selection["value"] = selected_method.get()
        root.destroy()

    ttk.Button(root, text="OK", command=confirm_selection).grid(
        row=2, column=0, padx=16, pady=(8, 16)
    )
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.update_idletasks()

    window_width = root.winfo_width()
    window_height = root.winfo_height()
    screen_x = (root.winfo_screenwidth() - window_width) // 2
    screen_y = (root.winfo_screenheight() - window_height) // 2
    root.geometry(f"+{screen_x}+{screen_y}")

    root.lift()
    root.attributes("-topmost", True)
    root.after(500, lambda: root.attributes("-topmost", False))
    method_dropdown.focus_set()
    root.mainloop()

    if selection["value"] is None:
        raise SystemExit("Welch averaging selection cancelled")
    return selection["value"]


def extract_analysis_intervals(raw) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    active_start: float | None = None
    annotations = sorted(raw.annotations, key=lambda item: item["onset"])

    for annotation in annotations:
        description = str(annotation["description"]).strip()
        onset = float(annotation["onset"])
        if description == ANALYSIS_ON:
            if active_start is not None:
                raise ValueError("ANALYSIS_ON occurs before the previous ANALYSIS_OFF")
            active_start = onset
        elif description == ANALYSIS_OFF:
            if active_start is None:
                raise ValueError("ANALYSIS_OFF occurs without a preceding ANALYSIS_ON")
            if onset <= active_start:
                raise ValueError("ANALYSIS_OFF must occur after ANALYSIS_ON")
            intervals.append((active_start, onset))
            active_start = None

    if active_start is not None:
        raise ValueError("The final ANALYSIS_ON has no matching ANALYSIS_OFF")
    if not intervals:
        raise ValueError("No ANALYSIS_ON - ANALYSIS_OFF interval was found")
    return intervals


def create_welch_segments_from_intervals(
    channel_signal_uv: np.ndarray,
    analysis_intervals: list[tuple[float, float]],
    sampling_frequency: float,
) -> np.ndarray:
    segment_length, _, step_length = psd_math.compute_welch_parameters(
        sampling_frequency
    )
    segment_batches: list[np.ndarray] = []

    for start_seconds, stop_seconds in analysis_intervals:
        start_sample = max(0, int(round(start_seconds * sampling_frequency)))
        stop_sample = min(
            channel_signal_uv.size,
            int(round(stop_seconds * sampling_frequency)),
        )
        interval_signal = channel_signal_uv[start_sample:stop_sample]
        if interval_signal.size < segment_length:
            continue

        segment_starts = range(
            0,
            interval_signal.size - segment_length + 1,
            step_length,
        )
        segment_batches.append(
            np.stack(
                [
                    interval_signal[start : start + segment_length]
                    for start in segment_starts
                ],
                axis=0,
            )
        )

    if not segment_batches:
        raise ValueError("Analysis intervals contain no complete Welch segment")
    return np.concatenate(segment_batches, axis=0)


def compute_robust_psd_limits(
    all_segment_power: np.ndarray,
    lower_percentile: float = 5.0,
    upper_percentile: float = 95.0,
) -> tuple[float, float]:
    all_segment_power = np.asarray(all_segment_power, dtype=np.float64)
    if all_segment_power.size == 0:
        raise ValueError("all_segment_power is empty")
    if not np.all(np.isfinite(all_segment_power)):
        raise ValueError("all_segment_power contains non-finite values")
    if not 0.0 <= lower_percentile < upper_percentile <= 100.0:
        raise ValueError("Invalid robust-normalization percentiles")

    robust_min, robust_max = np.percentile(
        all_segment_power,
        [lower_percentile, upper_percentile],
    )
    if np.isclose(robust_min, robust_max):
        robust_max = robust_min + np.finfo(np.float64).eps
    return float(robust_min), float(robust_max)


def safe_file_component(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value).strip(" .")
    return cleaned or "unnamed_channel"


def save_channel_psd_figure(
    frequencies: np.ndarray,
    representative_power: np.ndarray,
    all_segment_power: np.ndarray,
    header_index: int,
    header_name: str,
    averaging_method: str,
    output_path: Path,
) -> None:
    robust_min, robust_max = compute_robust_psd_limits(all_segment_power)
    robust_normalization = Normalize(
        vmin=robust_min,
        vmax=robust_max,
        clip=False,
    )
    figure, axis = plt.subplots(figsize=(12, 7), constrained_layout=True)
    notch_guide_frequencies = np.arange(
        psd_math.POWER_LINE_FREQUENCY,
        psd_math.MAX_ANALYSIS_FREQUENCY + psd_math.POWER_LINE_FREQUENCY,
        psd_math.POWER_LINE_FREQUENCY,
    )
    notch_guide_frequencies = notch_guide_frequencies[
        notch_guide_frequencies <= psd_math.MAX_ANALYSIS_FREQUENCY
    ]
    for notch_frequency in notch_guide_frequencies:
        axis.axvline(
            notch_frequency,
            color="#808080",
            linestyle="--",
            linewidth=0.8,
            alpha=0.7,
            zorder=0,
        )
    axis.plot(frequencies, representative_power, color="#707070", linewidth=0.7)
    points = axis.scatter(
        frequencies,
        representative_power,
        c=representative_power,
        cmap=PSD_SPECTRUM_COLORMAP,
        norm=robust_normalization,
        s=14,
        edgecolors="#202020",
        linewidths=0.15,
    )
    axis.set_title(f"{header_index}: {header_name} ({averaging_method} Welch PSD)")
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel("PSD (dB re 1 uV^2/Hz)")
    axis.set_xlim(psd_math.MIN_ANALYSIS_FREQUENCY, psd_math.MAX_ANALYSIS_FREQUENCY)
    axis.grid(alpha=0.2)

    colorbar = figure.colorbar(points, ax=axis, extend="both")
    colorbar.ax.set_title(ROBUST_COLORBAR_TITLE, fontsize=8, pad=10)
    colorbar.set_label("PSD (dB re 1 uV^2/Hz)")
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def generate_psd_figures(
    raw,
    figure_headers: list[tuple[int, str]],
    averaging_method: str,
    output_directory: Path,
    edf_stem: str,
) -> None:
    if averaging_method not in {"mean", "median"}:
        raise ValueError("averaging_method must be 'mean' or 'median'")

    sampling_frequency = edf_preprocessor.extract_sampling_frequency(raw)
    analysis_intervals = extract_analysis_intervals(raw)
    method_directory = output_directory / averaging_method
    method_directory.mkdir(parents=True, exist_ok=True)

    for sequence_number, (header_index, header_name) in enumerate(
        figure_headers, start=1
    ):
        print(
            f"Generating {averaging_method} PSD figure "
            f"{sequence_number}/{len(figure_headers)}: {header_name}"
        )
        channel_signal_uv = raw.get_data(picks=[header_index])[0] * 1e6
        filtered_signal_uv = psd_math.apply_powerline_notch_filter(
            channel_signal_uv, sampling_frequency
        )
        segments = create_welch_segments_from_intervals(
            filtered_signal_uv,
            analysis_intervals,
            sampling_frequency,
        )
        frequencies, all_segment_power = psd_math.compute_all_segment_power(
            segments, sampling_frequency
        )
        mean_result, median_result = psd_math.compute_representative_segment_power(
            frequencies, all_segment_power
        )
        representative_frequencies, representative_power = (
            mean_result if averaging_method == "mean" else median_result
        )
        representative_power_db = psd_math.convert_power_to_db(
            representative_power
        )
        all_segment_power_db = psd_math.convert_power_to_db(
            all_segment_power
        )

        output_name = (
            f"{safe_file_component(edf_stem)}_"
            f"{header_index:03d}_{safe_file_component(header_name)}.png"
        )
        save_channel_psd_figure(
            representative_frequencies,
            representative_power_db,
            all_segment_power_db,
            header_index,
            header_name,
            averaging_method,
            method_directory / output_name,
        )


if __name__ == "__main__":
    analysis_directory, analysis_file_name, output_directory = (
        get_analysis_edf_input()
    )
    print(f"Selected directory: {analysis_directory}")
    print(f"Selected EDF file: {analysis_file_name}")
    print(f"Figure output directory: {output_directory}")
    raw = edf_preprocessor.load_edf(
        analysis_directory,
        analysis_file_name,
        preload=False,
    )
    sampling_frequency = edf_preprocessor.extract_sampling_frequency(raw)
    excluded_headers = enumerate_excluded_headers(raw.ch_names)
    figure_headers = enumerate_figure_headers(raw.ch_names)

    print("Excluded from figure generation (0-based index):")
    for header_index, header_name in excluded_headers: print(f"- {header_index}: {header_name}")
    print(f"Figure-generation headers: {len(figure_headers)}")
    averaging_method = get_welch_averaging_method()
    generate_psd_figures(
        raw,
        figure_headers,
        averaging_method,
        output_directory,
        Path(analysis_file_name).stem,
    )
