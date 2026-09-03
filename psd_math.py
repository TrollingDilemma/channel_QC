## 1. imports
import numpy as np
from scipy.signal import iirnotch, sosfiltfilt, tf2sos


## 2. analysis parameters
WELCH_SEGMENT_LENGTH_SECONDS = 2.0  # sec
WELCH_OVERLAP_RATIO = 0.5  # *100%
MIN_ANALYSIS_FREQUENCY = 1.0  # Hz
MAX_ANALYSIS_FREQUENCY = 250.0  # Hz
POWER_LINE_FREQUENCY = 60.0  # Hz
NOTCH_FILTER_Q = 30.0


## 3. sampling-frequency-dependent Welch parameters
def compute_welch_parameters(sampling_frequency: float) -> tuple[int, int, int]:
    if not np.isfinite(sampling_frequency) or sampling_frequency <= 0:
        raise ValueError("sampling_frequency가 유효한 양수가 아님")

    segment_length_samples = int(
        sampling_frequency * WELCH_SEGMENT_LENGTH_SECONDS
    )
    overlap_samples = int(segment_length_samples * WELCH_OVERLAP_RATIO)
    step_samples = segment_length_samples - overlap_samples
    frequency_bin_length = sampling_frequency / segment_length_samples

    if not np.isclose(frequency_bin_length, 0.5):
        raise ValueError("FREQUENCY BIN LENGTH가 0.5 Hz가 아님")

    return segment_length_samples, overlap_samples, step_samples


## 4. 60 Hz harmonic notch filtering
def apply_powerline_notch_filter(
    signal: np.ndarray,
    sampling_frequency: float,
    powerline_frequency: float = POWER_LINE_FREQUENCY,
    quality_factor: float = NOTCH_FILTER_Q,
    axis: int = -1,
) -> np.ndarray:
    """분석 대역 내 60 Hz 정수배 성분을 zero-phase notch filtering한다."""
    signal = np.asarray(signal, dtype=np.float64)

    if signal.size == 0:
        raise ValueError("signal이 비어 있음")
    if not np.all(np.isfinite(signal)):
        raise ValueError("signal에 NaN 또는 무한대 값이 포함되어 있음")
    if sampling_frequency <= 0:
        raise ValueError("sampling_frequency는 0보다 커야 함")
    if powerline_frequency <= 0:
        raise ValueError("powerline_frequency는 0보다 커야 함")
    if quality_factor <= 0:
        raise ValueError("quality_factor는 0보다 커야 함")

    nyquist_frequency = sampling_frequency / 2.0
    maximum_notch_frequency = min(
        MAX_ANALYSIS_FREQUENCY,
        np.nextafter(nyquist_frequency, 0.0),
    )
    notch_frequencies = np.arange(
        powerline_frequency,
        maximum_notch_frequency + powerline_frequency,
        powerline_frequency,
        dtype=np.float64,
    )
    notch_frequencies = notch_frequencies[
        notch_frequencies <= maximum_notch_frequency
    ]

    if notch_frequencies.size == 0:
        return signal.copy()

    sos_sections = []
    for notch_frequency in notch_frequencies:
        numerator, denominator = iirnotch(
            w0=notch_frequency,
            Q=quality_factor,
            fs=sampling_frequency,
        )
        sos_sections.append(tf2sos(numerator, denominator))

    combined_sos = np.vstack(sos_sections)
    return sosfiltfilt(combined_sos, signal, axis=axis)


## 5. constant (0 Hz component) detrending per Welch segment
def detrend_constant(
    segment: np.ndarray,
    sampling_frequency: float,
) -> np.ndarray:
    segment = np.asarray(segment, dtype=np.float64)
    segment_length_samples, _, _ = compute_welch_parameters(sampling_frequency)
    if segment.ndim != 1:
        raise ValueError("segment가 1차원 배열이 아님")
    if segment.size != segment_length_samples:
        raise ValueError(
            f"segment 길이가 {segment_length_samples} samples가 아님"
        )
    if not np.all(np.isfinite(segment)):
        raise ValueError("segment에 NaN 또는 무한대 값이 포함되어 있음")
    detrended_segment = segment - np.mean(segment)
    return detrended_segment


## 6. Hanning window per Welch segment
def apply_hanning_window(detrended_segment: np.ndarray) -> np.ndarray:
    detrended_segment = np.asarray(detrended_segment, dtype=np.float64)
    hanning_window = np.hanning(detrended_segment.size)
    windowed_segment = detrended_segment * hanning_window
    return windowed_segment


## 7. FFT per Welch segment (ROI frequency = 1-250 Hz)
def compute_segment_fft(
    windowed_segment: np.ndarray,
    sampling_frequency: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return analysis frequencies and complex FFT coefficients."""
    windowed_segment = np.asarray(windowed_segment, dtype=np.float64)
    segment_length_samples, _, _ = compute_welch_parameters(sampling_frequency)
    if windowed_segment.ndim != 1:
        raise ValueError("windowed_segment가 1차원 배열이 아님")
    if windowed_segment.size != segment_length_samples:
        raise ValueError(
            f"windowed_segment 길이가 {segment_length_samples} samples가 아님"
        )
    fft_coefficients = np.fft.rfft(
        windowed_segment,
        n=segment_length_samples,
    )
    frequencies = np.fft.rfftfreq(
        segment_length_samples,
        d=1.0 / sampling_frequency,
    )
    analysis_mask = (
        (frequencies >= MIN_ANALYSIS_FREQUENCY)
        & (frequencies <= MAX_ANALYSIS_FREQUENCY)
    )

    analysis_frequencies = frequencies[analysis_mask]
    analysis_fft = fft_coefficients[analysis_mask]
    return analysis_frequencies, analysis_fft


## 8. Welch segment processing (steps 5-7)
def process_welch_segment(
    segment: np.ndarray,
    sampling_frequency: float,
) -> tuple[np.ndarray, np.ndarray]:
    detrended_segment = detrend_constant(segment, sampling_frequency)
    windowed_segment = apply_hanning_window(detrended_segment)
    analysis_frequencies, analysis_fft = compute_segment_fft(
        windowed_segment,
        sampling_frequency,
    )
    return analysis_frequencies, analysis_fft


## 9. power computation per Welch segment; PSD [uV^2/Hz]
def compute_segment_power(
    analysis_fft: np.ndarray,
    sampling_frequency: float,
) -> np.ndarray:
    analysis_fft = np.asarray(analysis_fft, dtype=np.complex128)
    segment_length_samples, _, _ = compute_welch_parameters(sampling_frequency)
    hanning_window = np.hanning(segment_length_samples)
    hanning_window_power = np.sum(hanning_window**2)
    segment_power = (np.abs(analysis_fft) ** 2) / (
        sampling_frequency * hanning_window_power
    )
    return segment_power


def convert_power_to_db(power: np.ndarray) -> np.ndarray:
    power = np.asarray(power, dtype=np.float64)
    if np.any(power < 0):
        raise ValueError("power contains negative values")
    if not np.all(np.isfinite(power)):
        raise ValueError("power contains non-finite values")

    minimum_positive_power = np.finfo(np.float64).tiny
    return 10.0 * np.log10(np.maximum(power, minimum_positive_power))


def compute_all_segment_power(
    segments: np.ndarray,
    sampling_frequency: float,
) -> tuple[np.ndarray, np.ndarray]:
    segments = np.asarray(segments, dtype=np.float64)
    segment_length_samples, _, _ = compute_welch_parameters(sampling_frequency)
    if segments.ndim != 2:
        raise ValueError("segments가 2차원 배열이 아님")
    if segments.shape[0] == 0:
        raise ValueError("segments가 비어 있음")
    if segments.shape[1] != segment_length_samples:
        raise ValueError(
            f"각 segment 길이가 {segment_length_samples} samples가 아님"
        )
    all_segment_power = []
    analysis_frequencies = None

    for segment in segments:
        frequencies, analysis_fft = process_welch_segment(
            segment,
            sampling_frequency,
        )
        segment_power = compute_segment_power(
            analysis_fft,
            sampling_frequency,
        )
        all_segment_power.append(segment_power)
        if analysis_frequencies is None:
            analysis_frequencies = frequencies

    all_segment_power = np.stack(all_segment_power, axis=0)
    return analysis_frequencies, all_segment_power


## 10. mean and median PSD over Welch segments
def compute_representative_segment_power(
    analysis_frequencies: np.ndarray,
    all_segment_power: np.ndarray,
) -> tuple[tuple[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]:
    analysis_frequencies = np.asarray(analysis_frequencies, dtype=np.float64)
    all_segment_power = np.asarray(all_segment_power, dtype=np.float64)

    mean_power = np.mean(all_segment_power, axis=0)
    median_power = np.median(all_segment_power, axis=0)

    mean_result = (analysis_frequencies, mean_power)
    median_result = (analysis_frequencies, median_power)
    return mean_result, median_result
