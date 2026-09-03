## 1. params definition for Welch
EEG_SAMPLING_FREQUENCY = 2048 # Hz
WELCH_SEGMENT_LENGTH_SECONDS = 2.0 # sec
WELCH_OVERLAP_RATIO  = 0.5 #  *100%

WELCH_SEGMENT_LENGTH_SAMPLES = int(EEG_SAMPLING_FREQUENCY * WELCH_SEGMENT_LENGTH_SECONDS)
WELCH_OVERLAP_SAMPLES = int(WELCH_SEGMENT_LENGTH_SAMPLES * WELCH_OVERLAP_RATIO)
WELCH_STEP_SAMPLES = WELCH_SEGMENT_LENGTH_SAMPLES - WELCH_OVERLAP_SAMPLES

## 2. constant(f=0Hz component) detrending per Welch segment
import numpy as np

def detrend_constant(segment: np.ndarray) -> np.ndarray:
    segment = np.asarray(segment, dtype=np.float64)
    if segment.ndim != 1:
        raise ValueError("segment가 1차원 배열이 아님")
    if segment.size != WELCH_SEGMENT_LENGTH_SAMPLES:
        raise ValueError(f"segment 길이가 {WELCH_SEGMENT_LENGTH_SAMPLES} samples가 아님")
    if not np.all(np.isfinite(segment)):
        raise ValueError("segment에 NaN 또는 무한대 값이 포함되어 있음")
    detrended_segment = segment - np.mean(segment)
    return detrended_segment

## 3. Hanning per Welch segment
def apply_hanning_window(detrended_segment: np.ndarray) -> np.ndarray:
    detrended_segment = np.asarray(detrended_segment, dtype=np.float64)
    hanning_window = np.hanning(WELCH_SEGMENT_LENGTH_SAMPLES)
    windowed_segment = detrended_segment * hanning_window
    return windowed_segment

## 4. FFT per Welch segment (ROI freq = 1-250Hz)
FREQUENCY_BIN_LENGTH = EEG_SAMPLING_FREQUENCY / WELCH_SEGMENT_LENGTH_SAMPLES # 0.5Hz
MIN_ANALYSIS_FREQUENCY = 1.0
MAX_ANALYSIS_FREQUENCY = 250.0
if not np.isclose(FREQUENCY_BIN_LENGTH, 0.5):
    raise ValueError("FREQUENCY BIN LENGTH가 0.5Hz가 아님")

def compute_segment_fft(windowed_segment: np.ndarray) -> tuple[np.ndarray, np.ndarray]: # returning complex number's coefficients
    windowed_segment = np.asarray(windowed_segment, dtype=np.float64)
    fft_coefficients = np.fft.rfft(windowed_segment, n=WELCH_SEGMENT_LENGTH_SAMPLES)
    frequencies = np.fft.rfftfreq(WELCH_SEGMENT_LENGTH_SAMPLES, d=1.0 / EEG_SAMPLING_FREQUENCY)
    analysis_mask = (frequencies >= MIN_ANALYSIS_FREQUENCY) & (frequencies <= MAX_ANALYSIS_FREQUENCY)

    analysis_frequencies = frequencies[analysis_mask]
    analysis_fft = fft_coefficients[analysis_mask]

    return analysis_frequencies, analysis_fft

## ☆ 1->4 connection
def process_welch_segment(segment: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    detrended_segment = detrend_constant(segment)
    windowed_segment = apply_hanning_window(detrended_segment)
    analysis_frequencies, analysis_fft = compute_segment_fft(windowed_segment)
    return analysis_frequencies, analysis_fft

## 5. computing power per Welch segment; PSD[uV^2/Hz]
HANNING_WINDOW = np.hanning(WELCH_SEGMENT_LENGTH_SAMPLES)
HANNING_WINDOW_POWER = np.sum(HANNING_WINDOW ** 2) # used for power normalization; correcting power-loss d/t hanning

def compute_segment_power(analysis_fft: np.ndarray) -> np.ndarray:
    analysis_fft = np.asarray(analysis_fft, dtype = np.complex128)
    segment_power = (np.abs(analysis_fft) ** 2) / (EEG_SAMPLING_FREQUENCY * HANNING_WINDOW_POWER) # unit: uV^2/Hz
    return segment_power

def compute_all_segment_power(segments: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    segments = np.asarray(segments, dtype=np.float64)
    all_segment_power = []
    analysis_frequencies = None

    for s in segments:
        frequencies, analysis_fft = process_welch_segment(s)
        segment_power = compute_segment_power(analysis_fft)
        all_segment_power.append(segment_power)
        if analysis_frequencies is None:
            analysis_frequencies = frequencies
    all_segment_power = np.stack(all_segment_power, axis=0)

    return analysis_frequencies, all_segment_power

## 6. mean & median PSD over-Welch-segment
def compute_representative_segment_power(analysis_frequencies: np.ndarray, all_segment_power: np.ndarray) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
    analysis_frequencies = np.asarray(analysis_frequencies, dtype=np.float64)
    all_segment_power = np.asarray(all_segment_power, dtype=np.float64)

    mean_power = np.mean(all_segment_power, axis=0)
    median_power = np.median(all_segment_power, axis=0)

    mean_result = [analysis_frequencies, mean_power]
    median_result = [analysis_frequencies, median_power]
    return mean_result, median_result