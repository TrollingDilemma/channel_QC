from pathlib import Path
from collections.abc import Mapping
import mne
import numpy as np
from numpy.typing import NDArray

## 1. edf loading
def load_edf(directory_path:str | Path, file_name:str, preload: bool=True) -> mne.io.BaseRaw:
    directory_path = Path(directory_path).expanduser()
    if not directory_path.exists():
        raise FileNotFoundError("directory 없음")
    if not directory_path.is_dir():
        raise NotADirectoryError("directory 아님")
    edf_path = directory_path / file_name
    if not edf_path.is_file():
        raise ValueError(f"파일 경로 아님: {edf_path}")
    raw = mne.io.read_raw_edf(edf_path, preload=preload, verbose=False)
    print_edf_metadata(raw)
    return raw


## 2. EDF metadata terminal output
def print_edf_metadata(raw: mne.io.BaseRaw) -> None:
    sampling_frequency = extract_sampling_frequency(raw)

    print(f"Sampling frequency: {sampling_frequency:g} Hz")
    print("Header names:")
    for header_name in raw.ch_names:
        print(f"- {header_name}")


## 3. sampling frequency
def extract_sampling_frequency(raw: mne.io.BaseRaw) -> float:
    sampling_frequency = float(raw.info["sfreq"])
    if not np.isfinite(sampling_frequency) or sampling_frequency <= 0:
        raise ValueError("sampling frequency가 유효한 양수가 아님")
    return sampling_frequency


## 4. channel-wise voltage timeseries
def extract_channel_timeseries(raw: mne.io.BaseRaw) -> dict[str, NDArray[np.float64]]:
    eeg_channel_indices = mne.pick_types(raw.info, eeg=True, exclude=[])
    if eeg_channel_indices.size == 0:
        raise ValueError("eeg channel 탐색되지 않음")

    eeg_channel_names = [raw.ch_names[i] for i in eeg_channel_indices]
    if len(eeg_channel_names) != len(set(eeg_channel_names)):
        raise ValueError("중복된 channel header")

    eeg_matrix = raw.get_data(picks=eeg_channel_indices)
    channel_data = {channel_name: eeg_matrix[row_i].copy() for row_i, channel_name in enumerate(eeg_channel_names)}

    return channel_data